"""فاز ۵۴ - API چت آنلاین عمومی سایت (بدون احراز هویت الزامی).

- POST /public/chat/session: ساخت/بازیابی نشست با توکن مرورگر؛ اگر بازدیدکننده
  لاین باشد (هدر Bearer معتبر) نشست به او متصل می‌شود (ذخیره بر اساس نام کاربری)،
  وگرنه هویت = توکن نشست + IP (ذخیره بر اساس IP در صورت عدم لاگین)؛
- GET  /public/chat/{token}/messages: تاریخچهٔ گفتگو (تداوم برای همان مرورگر)؛
- POST /public/chat/{token}/messages: ارسال پیام + پاسخ دستیار قاعده‌محور با
  کارت‌های اقدام (انتقال به صفحهٔ مرتبط: رزرو/ورود/مشاوران/خدمات)؛
- POST /public/chat/{token}/rating: نظر کاربر دربارهٔ خودِ گفتگو (۱ تا ۵ + توضیح).
"""
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_optional
from app.db.session import get_db
from app.models.public_chat import (
    CONTENT_MAX_LEN,
    RATING_COMMENT_MAX,
    PublicChatMessage,
    PublicChatSession,
)
from app.models.user import User
from app.services import public_chat as engine
from app.services.public_chat import check_rate_limit

router = APIRouter(prefix="/public/chat", tags=["public-chat"])

_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _get_session(db: Session, token: str) -> PublicChatSession:
    if not _TOKEN_RE.fullmatch(token or ""):
        raise HTTPException(status_code=422, detail="توکن نشست نامعتبر است")
    s = db.scalar(select(PublicChatSession).where(PublicChatSession.token == token))
    if s is None:
        raise HTTPException(status_code=404, detail="نشست گفتگو یافت نشد")
    return s


class SessionCreate(BaseModel):
    token: str = Field(min_length=8, max_length=64)
    visitor_name: str | None = Field(default=None, max_length=100)
    first_page: str | None = Field(default=None, max_length=200)


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=CONTENT_MAX_LEN)


class RatingCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=RATING_COMMENT_MAX)


@router.post("/session", status_code=200)
def open_session(
    payload: SessionCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User | None = Depends(get_current_user_optional),
) -> dict:
    """ساخت یا بازیابی نشست چت — هویت لایه‌لایه: کاربر لاگین / نام معرفی‌شده / IP."""
    if not _TOKEN_RE.fullmatch(payload.token or ""):
        raise HTTPException(status_code=422, detail="توکن نشست نامعتبر است")
    ip = _client_ip(request)
    session = db.scalar(select(PublicChatSession).where(PublicChatSession.token == payload.token))
    if session is None:
        session = PublicChatSession(
            token=payload.token,
            user_id=actor.id if actor else None,
            ip=ip,
            user_agent=(request.headers.get("user-agent") or "")[:300] or None,
            first_page=(payload.first_page or "")[:200] or None,
        )
        db.add(session)
    else:
        # پیوست هویت: اگر همان مرورگر بعداً لاین شد، نشست به کاربر متصل می‌شود
        if actor is not None and session.user_id is None:
            session.user_id = actor.id
        if session.ip != ip:
            # آخرین IP دیده‌شده نگه داشته می‌شود (کاربران اینترنت موبایل IPشان می‌چرخد)
            session.ip = ip
    if payload.visitor_name is not None:
        name = payload.visitor_name.strip()[:100]
        if name:
            session.visitor_name = name
    db.commit()
    db.refresh(session)
    return {
        "session": engine.session_out(db, session, actor),
        "messages": engine.session_messages(db, session),
    }


@router.get("/{token}/messages")
def get_messages(token: str, db: Session = Depends(get_db)) -> dict:
    session = _get_session(db, token)
    return {"items": engine.session_messages(db, session)}


@router.post("/{token}/messages", status_code=201)
def send_message(
    token: str,
    payload: MessageCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User | None = Depends(get_current_user_optional),
) -> dict:
    """پیام بازدیدکننده + پاسخ دستیار (قاعده‌محور، با کارت اقدام)."""
    if not check_rate_limit(token):
        raise HTTPException(status_code=429, detail="تعداد پیام‌ها زیاد است؛ کمی بعد تلاش کنید")
    session = _get_session(db, token)
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="متن پیام خالی است")
    if session.status != "open":
        raise HTTPException(status_code=409, detail="این گفتگو بسته شده است؛ گفتگوی جدیدی شروع کنید")

    user_row = PublicChatMessage(
        session_id=session.id, role="user", content=content[:CONTENT_MAX_LEN]
    )
    db.add(user_row)

    # فاز ۵۶: اگر اپراتور پذیرش اخیراً پاسخ داده، دستیار خودکار ساکت می‌ماند
    # (پاسخ انسانی در حال جریان است)؛ در غیر این صورت پاسخ قاعده‌محور برمی‌گردد.
    # فاز ۷۰: fail-soft — هر خطای موتور پاسخ هرگز کل endpoint را 500 نمی‌کند
    # (باگ میدانی فاز ۵۶: NameError ثابت‌های مدل → «خطا در ارسال پیام» برای
    # همهٔ پیام‌ها؛ حالا خطا لاگ می‌شود و پاسخ امن برمی‌گردد).
    assistant_row: PublicChatMessage | None = None
    if not engine.operator_engaged(db, session):
        try:
            reply = engine.build_reply(db, content)
        except Exception:  # noqa: BLE001 — پاسخ امن جای خطای 500
            import logging

            logging.getLogger("rosepsy.public_chat").exception(
                "build_reply failed — safe fallback returned")
            reply = engine.PublicChatReply(
                "پیام شما ثبت شد؛ اما در تولید پاسخ خودکار خطایی رخ داد. "
                "لطفاً دوباره تلاش کنید یا از صفحه «رزرو نوبت» استفاده کنید.",
                actions=[{"label": "صفحهٔ رزرو نوبت", "url": "/booking", "kind": "primary"}],
                intent="fallback_error",
            )
        assistant_row = PublicChatMessage(
            session_id=session.id,
            role="assistant",
            content=reply.content,
            actions=reply.actions or None,
            quick_replies=reply.quick_replies or None,
            intent=reply.intent,
        )
        db.add(assistant_row)
    session.message_count = (session.message_count or 0) + (2 if assistant_row else 1)
    db.commit()
    if assistant_row is not None:
        db.refresh(assistant_row)

    return {
        "message": engine.message_out(assistant_row) if assistant_row else None,
        "session": engine.session_out(db, session, actor),
    }


@router.post("/{token}/rating")
def rate_session(token: str, payload: RatingCreate, db: Session = Depends(get_db)) -> dict:
    """نظر کاربر دربارهٔ خودِ گفتگو — یک بار ثبت می‌شود و قابل ویرایش است."""
    session = _get_session(db, token)
    session.rating = int(payload.rating)
    session.rating_comment = (payload.comment or "").strip()[:RATING_COMMENT_MAX] or None
    db.commit()
    return {"status": "ok", "rating": session.rating}
