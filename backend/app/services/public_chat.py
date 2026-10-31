"""فاز ۵۴ - چت آنلاین عمومی سایت — موتور پاسخ قاعده‌محور (همان خط مشی D07).

اصول:
- پاسخ «قاعده‌محور و قطعی» بدون مدل بیرونی برای بازدیدکنندهٔ عمومی —
  بدون کلید، بدون هزینه، بدون نشت دادهٔ بالینی (همان مرز فاز ۳۵)؛
- علاوه بر متن، «کارت اقدام» برمی‌گرداند: دکمهٔ انتقال بازدیدکننده به
  صفحهٔ مرتبط (رزرو نوبت با مشاور دلخواه، ورود/ثبت‌نام در سامانه،
  فهرست مشاوران، خدمات، تماس) — «معرفی متقاضی و انتقال به صفحهٔ مرتبط»؛
- «پاسخ پیشنهادی» (quick replies) مسیر گفتگوی بعدی را ساده می‌کند؛
- نیت رزرو → فهرست مشاوران قابل رزرو از DB (صلاحیت معتبر) با دکمهٔ
  «رزرو از این مشاور» که به /booking?counselor=<id> می‌رود (پیش‌انتخاب)؛
- سقف نرخ: حداکثر RATE_LIMIT_PER_MINUTE پیام در دقیقه برای هر نشست
  (in-process؛ در نبود Redis هم ایمن می‌ماند).
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog import Service, ServiceStatus
from app.models.public_chat import (
    CONTENT_MAX_LEN,
    OPERATOR_NAME_MAX,
    OPERATOR_TAKEOVER_MINUTES,
    PublicChatMessage,
    PublicChatSession,
)

RATE_LIMIT_PER_MINUTE = 20

_DISCLAIMER = "این گفتگو جایگزین مشاورهٔ حرفه‌ای نیست؛ برای تصمیم بالینی با مشاور تماس بگیرید."

_DEFAULT_QUICK_REPLIES = [
    "می‌خواهم نوبت رزرو کنم",
    "مشاوران شما چه کسانی هستند؟",
    "خدمات و قیمت‌ها",
    "چطور وارد سامانه شوم؟",
    "ساعات کاری",
]

_GREETING_QUICK_REPLIES = [
    "می‌خواهم نوبت رزرو کنم",
    "مشاوران شما چه کسانی هستند؟",
    "خدمات و قیمت‌ها",
    "ساعات کاری",
]

# ---------------------------------------------------------------------------
# دانش قاعده‌محور — کلمات کلیدی → پاسخ + کارت‌های اقدام + نیت
# ---------------------------------------------------------------------------

_LOGIN_ACTIONS = [
    {"label": "ورود به سامانه", "url": "/panel/", "kind": "primary"},
    {"label": "رزرو نوبت بدون ثبت‌نام", "url": "/booking", "kind": "secondary"},
]

_COUNSELORS_ACTIONS = [
    {"label": "مشاهده مشاوران و رزرو", "url": "/booking", "kind": "primary"},
]

_SERVICES_ACTIONS = [
    {"label": "مشاهده خدمات روان‌درمانی", "url": "/services/psychotherapy", "kind": "secondary"},
    {"label": "رزرو نوبت", "url": "/booking", "kind": "primary"},
]

_CONTACT_ACTIONS = [
    {"label": "فرم تماس و درخواست مشاوره", "url": "/#contact", "kind": "primary"},
]

_BOOKING_ACTIONS = [
    {"label": "صفحهٔ رزرو نوبت", "url": "/booking", "kind": "primary"},
]


def _text_actions(actions: list[dict] | None = None) -> list[dict]:
    base = list(actions or [])
    return base


class PublicChatReply:
    """نتیجهٔ موتور پاسخ: متن + کارت‌های اقدام + پاسخ‌های پیشنهادی + نیت."""

    __slots__ = ("content", "actions", "quick_replies", "intent")

    def __init__(self, content: str, *, actions: list[dict] | None = None,
                 quick_replies: list[str] | None = None, intent: str = "fallback") -> None:
        self.content = content
        self.actions = _text_actions(actions)
        self.quick_replies = list(quick_replies) if quick_replies is not None else list(_DEFAULT_QUICK_REPLIES)
        self.intent = intent


def _has(text: str, words: tuple[str, ...]) -> bool:
    return any(w in text for w in words)


# ---------------------------------------------------------------- راهنمای داده
def _counselor_cards(db: Session, limit: int = 4) -> list[dict]:
    """کارت مشاوران قابل رزرو (صلاحیت معتبر) با دکمهٔ رزرو پیش‌انتخابی."""
    # import دیرهنگام برای پرهیز از چرخهٔ واردات
    from app.services.qualification import bookable_counselors

    cards: list[dict] = []
    for c in bookable_counselors(db)[:limit]:
        cards.append({
            "label": f"رزرو از {c.first_name} {c.last_name}",
            "url": f"/booking?counselor={c.id}",
            "kind": "counselor",
            "name": f"{c.first_name} {c.last_name}",
            "specialty": c.specialty or c.professional_title or "",
            "photo_url": f"/api/v1/public/counselors/{c.id}/photo" if c.photo_path else None,
        })
    return cards


def _service_rows(db: Session, limit: int = 5) -> list[dict]:
    """خدمات فعال + قیمت جاری از تعرفهٔ نسخه‌دار (مثل /api/v1/public/services)."""
    from app.api.v1.catalog import current_tariff

    items = db.scalars(
        select(Service).where(Service.status == ServiceStatus.ACTIVE).order_by(Service.title).limit(limit)
    ).all()
    out = []
    for s in items:
        t = current_tariff(db, s.id)
        out.append({
            "title": s.title,
            "duration_minutes": s.duration_minutes,
            "price": (f"{int(t.amount):,} {t.currency}" if t and t.amount is not None else None),
        })
    return out


def _format_services_text(rows: list[dict]) -> str:
    if not rows:
        return (
            "خدمات ما شامل مشاورهٔ فردی، زوج‌درمانی، روان‌درمانی کودک و نوجوان و درمان‌های تخصصی است. "
            "برای دیدن جزئیات هر خدمت و قیمت آن به صفحهٔ خدمات بروید."
        )
    lines = ["خدمات فعال ما:"]
    for r in rows:
        price = f" — قیمت: {r['price']}" if r["price"] else ""
        duration = f" ({r['duration_minutes']} دقیقه)" if r["duration_minutes"] else ""
        lines.append(f"• {r['title']}{duration}{price}")
    lines.append("قیمت‌ها بر پایهٔ تعرفهٔ جاری است و پس از انتخاب مشاور و زمان، نوبت شما ثبت می‌شود.")
    return "\n".join(lines)


# ---------------------------------------------------------------- موتور نیت
def build_reply(db: Session, content: str) -> PublicChatReply:
    """تشخیص نیت از متن فارسی/انگلیسی بازدیدکننده و ساخت پاسخ + کارت‌های اقدام."""
    text = (content or "").strip().lower()

    # ۱) نیت رزرو نوبت — مهم‌ترین مسیر تجاری
    # (بدون «وقت» تنها تا «وقت بخیر» به‌اشتباه رزرو نشود)
    if _has(text, ("نوبت", "رزرو", "وقت دار", "appointment", "booking", "نوبه")) and "ساعات" not in text:
        cards = _counselor_cards(db)
        body = (
            "برای رزرو نوبت کافی است در صفحهٔ «رزرو نوبت» مشاور دلخواه و سپس زمان آزاد را انتخاب کنید؛ "
            "زمان انتخابی تا تکمیل اطلاعات برای شما نگه داشته می‌شود و پذیرش برای تأیید نهایی تماس می‌گیرد."
        )
        if cards:
            body += "\nاز میان مشاوران زیر می‌توانید همین‌جا انتخاب کنید:"
        else:
            body += " در حال حاضر مشاوری برای رزرو فعال نیست؛ بعداً مراجعه کنید."
        return PublicChatReply(
            body,
            actions=(cards + _BOOKING_ACTIONS) if cards else _BOOKING_ACTIONS,
            quick_replies=["خدمات و قیمت‌ها", "ساعات کاری", "چطور وارد سامانه شوم؟"],
            intent="booking",
        )

    # ۲) قیمت خدمات — پیش از «مشاور» تا «قیمت مشاوره چنده؟» درست مسیر قیمت برود
    if _has(text, ("قیمت", "هزینه", "تعرفه", "تومان", "چند", "cost", "price", "fee")):
        rows = _service_rows(db)
        return PublicChatReply(
            _format_services_text(rows),
            actions=_SERVICES_ACTIONS,
            quick_replies=["می‌خواهم نوبت رزرو کنم", "مشاوران شما چه کسانی هستند؟"],
            intent="pricing",
        )

    # ۳) نیت مشاوران
    if _has(text, ("مشاور", "روان‌درمانگر", "رواندرمانگر", "روانشناس", "روان‌شناس", "متخصص", "دکتر", "counselor")):
        cards = _counselor_cards(db)
        body = (
            "مشاوران و روان‌درمانگران ما تیمی دارای مجوز و با تخصص‌های گوناگون هستند "
            "(روان‌درمانی فردی، زوج‌درمانی، کودک و نوجوان، افسردگی و اضطراب و…)."
        )
        if cards:
            body += "\nبرای دیدن نوبت‌های آزاد یکی از مشاوران زیر را انتخاب کنید:"
        return PublicChatReply(
            body,
            actions=(cards + _COUNSELORS_ACTIONS) if cards else _COUNSELORS_ACTIONS,
            quick_replies=["می‌خواهم نوبت رزرو کنم", "خدمات و قیمت‌ها"],
            intent="counselors",
        )

    # ۴) ورود / ثبت‌نام — معرفی متقاضی به سامانه
    if _has(text, ("ورود", "وارد", "ثبت نام", "ثبت‌نام", "حساب", "لاگین", "login", "register", "signup", "رمز")):
        return PublicChatReply(
            "برای استفاده از امکانات کامل (کارتابل، سفارش‌ها، آزمون‌ها و چت داخلی) وارد سامانه شوید؛ "
            "اگر حساب ندارید، از صفحهٔ ورود می‌توانید ثبت‌نام کنید. رزرو نوبت بدون ثبت‌نام هم ممکن است.",
            actions=_LOGIN_ACTIONS,
            quick_replies=["می‌خواهم نوبت رزرو کنم", "مشاوران شما چه کسانی هستند؟"],
            intent="login",
        )

    # ۵) خدمات
    if _has(text, ("خدمت", "خدمات", "درمان", "کارگاه", "دوره", "مشاوره", "service")):
        rows = _service_rows(db)
        return PublicChatReply(
            _format_services_text(rows),
            actions=_SERVICES_ACTIONS,
            quick_replies=["می‌خواهم نوبت رزرو کنم", "قیمت خدمات"],
            intent="services",
        )

    # ۶) ساعات کاری
    if _has(text, ("ساعت", "کاری", "باز", "تعطیل", "hours")):
        return PublicChatReply(
            "پذیرش سامانه شنبه تا پنجشنبه پاسخگوی شماست؛ زمان‌های آزاد هر مشاور را در صفحهٔ "
            "«رزرو نوبت» به‌صورت زنده می‌بینید و همان‌ها را می‌توانید رزرو کنید.",
            actions=_BOOKING_ACTIONS,
            quick_replies=["می‌خواهم نوبت رزرو کنم", "تماس با شما"],
            intent="hours",
        )

    # ۷) تماس / پشتیبانی
    if _has(text, ("تماس", "تلفن", "شماره", "آدرس", "ایمیل", "پشتیبانی", "contact", "پیگیری")):
        return PublicChatReply(
            "برای تماس، از فرم «درخواست مشاوره» در همین سایت استفاده کنید یا وارد سامانه شوید و تیکت پشتیبانی بزنید؛ "
            "پاسخ در اولین فرصت کاری داده می‌شود. اگر نوبت رزرو کرده‌اید، پذیرش خودش با شما تماس می‌گیرد.",
            actions=_CONTACT_ACTIONS + [{"label": "ورود به سامانه (تیکت پشتیبانی)", "url": "/panel/", "kind": "secondary"}],
            quick_replies=["می‌خواهم نوبت رزرو کنم", "چطور وارد سامانه شوم؟"],
            intent="contact",
        )

    # ۸) سلام و احوال‌پرسی
    if _has(text, ("سلام", "درود", "خسته نباشید", "وقت بخیر", "hello", "hi ", "سلام علیکم")) or text in ("سلام", "hi", "hello"):
        return PublicChatReply(
            "سلام! خوش آمدید. من دستیار آنلاین Rosepsy هستم؛ دربارهٔ نوبت‌دهی، مشاوران، خدمات و قیمت‌ها "
            "یا نحوهٔ ورود به سامانه می‌توانم راهنمایی کنم. چه کاری برایتان انجام دهم؟",
            quick_replies=_GREETING_QUICK_REPLIES,
            intent="greeting",
        )

    # ۹) تشکر
    if _has(text, ("ممنون", "مرسی", "سپاس", "متشکر", "thanks", "thank")):
        return PublicChatReply(
            "خواهش می‌کنم! اگر چیز دیگری لازم داشتید در خدمتم. نظر شما دربارهٔ این گفتگو هم برای ما ارزشمند است.",
            quick_replies=["می‌خواهم نوبت رزرو کنم", "خدمات و قیمت‌ها"],
            intent="thanks",
        )

    # ۱۰) پیش‌فرض — هدایت شفاف
    return PublicChatReply(
        "این پرسش خارج از دامنهٔ من است؛ اما دربارهٔ نوبت‌دهی، مشاوران، خدمات و قیمت‌ها، ساعات کاری و "
        "ورود به سامانه می‌توانم کمکتان کنم. یکی از گزینه‌های زیر را انتخاب کنید یا پرسشتان را ساده‌تر بپرسید.",
        actions=_BOOKING_ACTIONS,
        quick_replies=_DEFAULT_QUICK_REPLIES,
        intent="fallback",
    )


def disclaimer() -> str:
    return _DISCLAIMER


# ---------------------------------------------------------------- سقف نرخ
_rate_bucket: dict[str, deque[float]] = defaultdict(deque)


def check_rate_limit(token: str) -> bool:
    """True = مجاز؛ False = سقف پر شده (۴۲۹). پنجرهٔ ۶۰ ثانیه in-process."""
    now = time.monotonic()
    bucket = _rate_bucket[token]
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= RATE_LIMIT_PER_MINUTE:
        return False
    bucket.append(now)
    return True


# ---------------------------------------------------------------- چرخهٔ نشست
def session_messages(db: Session, session: PublicChatSession, limit: int = 200) -> list[dict]:
    rows = db.scalars(
        select(PublicChatMessage)
        .where(PublicChatMessage.session_id == session.id)
        .order_by(PublicChatMessage.created_at, PublicChatMessage.id)
        .limit(limit)
    ).all()
    return [message_out(r) for r in rows]


def message_out(r: PublicChatMessage) -> dict:
    return {
        "id": str(r.id),
        "role": r.role,
        "content": r.content,
        "sender_name": r.sender_name,
        "actions": r.actions,
        "quick_replies": r.quick_replies,
        "intent": r.intent,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


# ---------------------------------------------------------------- فاز ۵۶ - حضور اپراتور
def operator_engaged(db: Session, session: PublicChatSession) -> bool:
    """True اگر اپراتور اخیراً در گفتگو پاسخ داده باشد — دستیار خودکار ساکت می‌شود
    تا پاسخ انسانی پذیرش با پیام قاعده‌محور دوباره‌گویی نشود."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=OPERATOR_TAKEOVER_MINUTES)
    row = db.scalar(
        select(PublicChatMessage.id)
        .where(
            PublicChatMessage.session_id == session.id,
            PublicChatMessage.role == "operator",
            PublicChatMessage.created_at >= cutoff,
        )
        .limit(1)
    )
    return row is not None


def operator_reply(
    db: Session, session: PublicChatSession, content: str, sender_name: str
) -> PublicChatMessage:
    """ثبت پاسخ زندهٔ اپراتور پذیرش/مدیر در گفتگوی عمومی (فاز ۵۶)."""
    msg = PublicChatMessage(
        session_id=session.id,
        role="operator",
        content=content[:CONTENT_MAX_LEN],
        sender_name=(sender_name or "پذیرش")[:OPERATOR_NAME_MAX],
    )
    db.add(msg)
    session.message_count = (session.message_count or 0) + 1
    db.commit()
    db.refresh(msg)
    return msg


def session_out(db: Session, session: PublicChatSession, user) -> dict:
    """خلاصهٔ نشست برای کلاینت — هویت شفاف (کاربر/مهمان) بدون افشای IP."""
    if session.user_id and user is not None and str(user.id) == str(session.user_id):
        display_name = user.username
        identity = "user"
    elif session.visitor_name:
        display_name = session.visitor_name
        identity = "guest"
    else:
        display_name = "مهمان"
        identity = "guest"
    return {
        "token": session.token,
        "identity": identity,
        "display_name": display_name,
        "visitor_name": session.visitor_name,
        "is_registered": session.user_id is not None,
        "status": session.status,
        "rating": session.rating,
        "rating_comment": session.rating_comment,
        "message_count": session.message_count,
        "disclaimer": _DISCLAIMER,
    }
