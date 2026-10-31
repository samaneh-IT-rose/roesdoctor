"""فاز ۷۰ - API پروندهٔ مشاورهٔ کاربر.

- GET  /me/counseling-file            پروندهٔ خودِ کاربر (هر حساب واردشده):
                                       شمارهٔ پرونده + تاریخچهٔ آزمون‌ها و
                                       مشاوره‌ها به همراه زمان (خط زمانی).
- GET  /counseling-files              فهرست پرونده‌های کاربران برای پذیرش/مدیر
                                       (جست‌وجو بر نام/نام کاربری/شمارهٔ پرونده).
- GET  /counseling-files/{user_id}    جزئیات پروندهٔ یک کاربر (همان خط زمانی)
                                       برای کارکنان — «پروندهٔ مشاوره برای
                                       هر کاربر» از نگاه پذیرش.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.models.counseling_file import UserCounselingFile
from app.models.psych_test import PsychAttempt
from app.models.user import User
from app.services import counseling_file as cf

router = APIRouter(tags=["counseling-files"])

FILE_VIEW_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER", "TECHNICAL_SUPERVISOR", "RECEPTION", "COUNSELOR")


@router.get("/me/counseling-file")
def my_counseling_file(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    """پروندهٔ مشاورهٔ خودِ کاربر — ساخت خودکار در اولین بازدید (idempotent)."""
    return cf.file_out(db, actor, limit=100)


@router.get("/counseling-files")
def list_counseling_files(
    q: str = Query(default="", max_length=100),
    page: int = Query(default=1, ge=1, le=1_000_000),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*FILE_VIEW_ROLES)),
) -> dict:
    """فهرست پرونده‌های مشاورهٔ کاربران + تعداد آزمون هر کاربر."""
    base = (
        select(UserCounselingFile, User)
        .join(User, UserCounselingFile.user_id == User.id)
    )
    if (term := (q or "").strip()):
        like = f"%{term}%"
        base = base.where(or_(
            User.display_name.ilike(like),
            User.username.ilike(like),
            User.mobile.ilike(like),
            UserCounselingFile.file_code.ilike(like),
        ))
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.execute(
        base.order_by(UserCounselingFile.last_activity_at.desc().nullslast(),
                      UserCounselingFile.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()

    attempt_counts: dict[uuid.UUID, int] = {}
    user_ids = [f.user_id for f, _u in rows]
    if user_ids:
        grouped = db.execute(
            select(PsychAttempt.user_id, func.count())
            .where(PsychAttempt.user_id.in_(user_ids))
            .group_by(PsychAttempt.user_id)
        ).all()
        attempt_counts = {uid: int(n) for uid, n in grouped}

    items = [{
        "user_id": str(u.id),
        "file_code": f.file_code,
        "display_name": u.display_name,
        "username": u.username,
        "mobile": u.mobile,
        "attempt_count": attempt_counts.get(f.user_id, 0),
        "last_activity_at": (
            f.last_activity_at.isoformat() if f.last_activity_at else None
        ),
        "created_at": f.created_at.isoformat() if f.created_at else None,
        "staff_note": f.staff_note,
    } for f, u in rows]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/counseling-files/{user_id}")
def counseling_file_detail(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*FILE_VIEW_ROLES)),
) -> dict:
    """پروندهٔ مشاورهٔ یک کاربر — خط زمانی کامل آزمون‌ها و مشاوره‌ها."""
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد")
    return cf.file_out(db, u, limit=200)
