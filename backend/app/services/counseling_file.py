"""فاز ۷۰ - سرویس پروندهٔ مشاورهٔ کاربر — ساخت خودکار + خط زمانی تاریخچه.

هر کاربر (متقاضی آزمون یا رزروکنندهٔ مشاوره) یک «پروندهٔ مشاوره» دارد که
تاریخچهٔ آزمون‌ها و مشاوره‌های انجام‌شده را به همراه زمانشان نگه می‌دارد:

- اقلام آزمون: psych_attempts (عنوان ابزار، نمره، تفسیر، زمان، دیده‌شده، پرونده)؛
- اقلام مشاوره: consultation_requests که از دو راه به کاربر می‌رسند —
  (۱) اتصال applicant.user_id، (۲) تطابق موبایل (حساب رزرو آنلاین
  username=موبایل نرمال‌شده)؛
- اقلام نوبت: appointments روی پرونده‌های بالینی همان کاربر.

خط زمانی فقط «خواندن» از جداول منبع است؛ جدول user_counseling_files فقط
هویت پرونده (شمارهٔ یکتا) و جمع‌بندی را نگه می‌دارد تا هیچ داده‌ای دوباره
نویسی نشود (منبع واحد حقیقت).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.case import Case
from app.models.counseling_file import UserCounselingFile
from app.models.consultation import ConsultationRequest
from app.models.people import Applicant
from app.models.psych_test import PsychAttempt, PsychTest
from app.models.user import User


def ensure_file(db: Session, user: User) -> UserCounselingFile:
    """ساخت idempotent پروندهٔ مشاوره برای کاربر — با اولین آزمون/رزرو ساخته می‌شود."""
    f = db.scalar(select(UserCounselingFile).where(UserCounselingFile.user_id == user.id))
    if f is not None:
        return f
    f = UserCounselingFile(
        user_id=user.id,
        # شمارهٔ قطعی از خود شناسهٔ کاربر — یکتا بدون شرط رقابتی
        file_code=f"UF-{user.id.hex[:10].upper()}",
        last_activity_at=datetime.now(timezone.utc),
    )
    db.add(f)
    db.flush()
    return f


def touch_file(db: Session, user_id: uuid.UUID) -> None:
    """به‌روزرسانی زمان آخرین فعالیت پرونده (پس از آزمون/رزرو جدید)."""
    f = db.scalar(select(UserCounselingFile).where(UserCounselingFile.user_id == user_id))
    if f is not None:
        f.last_activity_at = datetime.now(timezone.utc)


def _user_mobile_keys(user: User) -> list[str]:
    """کلیدهای موبایل کاربر برای تطابق درخواست‌های مشاوره (بدون تکرار)."""
    keys: list[str] = []
    for v in (user.mobile, user.username):
        s = (v or "").strip()
        if s and s not in keys:
            keys.append(s)
    return keys


def user_applicant_ids(db: Session, user_id: uuid.UUID) -> list[uuid.UUID]:
    return db.scalars(
        select(Applicant.id).where(Applicant.user_id == user_id)
    ).all()


def timeline(
    db: Session,
    user: User,
    *,
    limit: int = 100,
    kinds: tuple[str, ...] | None = None,
) -> list[dict]:
    """خط زمانی تاریخچهٔ کاربر — همهٔ اقلام با زمان، جدیدترین اول.

    kinds اختیاری برای فیلتر ("psych_test" | "consultation" | "appointment").
    """
    want = set(kinds) if kinds else {"psych_test", "consultation", "appointment"}
    items: list[dict] = []

    # ۱) آزمون‌ها
    if "psych_test" in want:
        rows = db.execute(
            select(PsychAttempt, PsychTest)
            .join(PsychTest, PsychAttempt.test_id == PsychTest.id)
            .where(PsychAttempt.user_id == user.id)
            .order_by(PsychAttempt.created_at.desc())
            .limit(limit)
        ).all()
        for a, t in rows:
            items.append({
                "kind": "psych_test",
                "id": str(a.id),
                "title": t.title,
                "at": a.created_at.isoformat() if a.created_at else None,
                "score": int(a.score or 0),
                "interpretation_label": a.interpretation_label,
                "viewed": a.viewed_at is not None,
                "case_id": str(a.case_id) if a.case_id else None,
                "test_slug": t.slug,
            })

    # ۲) درخواست‌ها/رزروهای مشاوره (اتصال applicant یا موبایل)
    if "consultation" in want:
        applicant_ids = user_applicant_ids(db, user.id)
        mobile_keys = _user_mobile_keys(user)
        conds = []
        if applicant_ids:
            conds.append(ConsultationRequest.applicant_id.in_(applicant_ids))
        if mobile_keys:
            conds.append(ConsultationRequest.mobile.in_(mobile_keys))
        if conds:
            rows = db.scalars(
                select(ConsultationRequest)
                .where(or_(*conds))
                .order_by(ConsultationRequest.created_at.desc())
                .limit(limit)
            ).all()
            for r in rows:
                items.append({
                    "kind": "consultation",
                    "id": str(r.id),
                    "title": r.topic or "درخواست مشاوره",
                    "at": r.created_at.isoformat() if r.created_at else None,
                    "status": r.status,
                    "payment_status": r.payment_status,
                    "preferred_start_at": (
                        r.preferred_start_at.isoformat() if r.preferred_start_at else None
                    ),
                    "case_id": str(r.case_id) if r.case_id else None,
                })

    # ۳) نوبت‌های پرونده‌های بالینی کاربر
    if "appointment" in want:
        applicant_ids = user_applicant_ids(db, user.id)
        case_ids = (
            db.scalars(select(Case.id).where(Case.applicant_id.in_(applicant_ids))).all()
            if applicant_ids else []
        )
        if case_ids:
            rows = db.execute(
                select(Appointment, Case)
                .join(Case, Appointment.case_id == Case.id)
                .where(Appointment.case_id.in_(case_ids))
                .order_by(Appointment.scheduled_at.desc())
                .limit(limit)
            ).all()
            for ap, c in rows:
                items.append({
                    "kind": "appointment",
                    "id": str(ap.id),
                    "title": f"نوبت — پروندهٔ {c.case_number}",
                    "at": ap.scheduled_at.isoformat() if ap.scheduled_at else None,
                    "status": ap.status,
                    "location": ap.location,
                    "case_number": c.case_number,
                })

    items.sort(key=lambda x: x.get("at") or "", reverse=True)
    return items[:limit]


def file_out(db: Session, user: User, *, limit: int = 100) -> dict:
    """خروجی کامل پروندهٔ مشاوره برای API (پرونده + جمع‌بندی + اقلام)."""
    f = ensure_file(db, user)
    items = timeline(db, user, limit=limit)
    counts = {
        "psych_tests": sum(1 for i in items if i["kind"] == "psych_test"),
        "consultations": sum(1 for i in items if i["kind"] == "consultation"),
        "appointments": sum(1 for i in items if i["kind"] == "appointment"),
    }
    return {
        "file": {
            "id": str(f.id),
            "file_code": f.file_code,
            "staff_note": f.staff_note,
            "created_at": f.created_at.isoformat() if f.created_at else None,
            "last_activity_at": (
                f.last_activity_at.isoformat() if f.last_activity_at else None
            ),
        },
        "user": {
            "id": str(user.id),
            "display_name": user.display_name,
            "username": user.username,
            "mobile": user.mobile,
        },
        "counts": counts,
        "items": items,
    }
