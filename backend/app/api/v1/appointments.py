import uuid
from datetime import datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.services.case_access import counselor_can_access
from app.models.appointment import Appointment, AppointmentStatus
from app.models.catalog import Service, ServiceStatus
from app.models.case import Case, CaseStatus
from app.models.people import Applicant, Counselor, CounselorAvailability
from app.schemas.schedule import AppointmentCreate, AppointmentUpdate
from app.services.audit import record_audit

router = APIRouter(tags=["appointments"])

VIEW_ROLES = ("ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR")
STAFF_ROLES = ("ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR")


def _roles(actor) -> set[str]:
    return {r.code for r in actor.roles}


def availability_conflict(db: Session, counselor_id, scheduled_at) -> str | None:
    """فاز ۷۴ — بررسی زمان نوبت با روزها/ساعت‌های مشاورهٔ مشاور.

    None = مجاز؛ رشته = پیام خطا. اگر مشاور هیچ بازه‌ای تعریف نکرده باشد
    رفتار قبلی (بدون محدودیت) برقرار است. قرارداد زمانی سامانه: مقدار
    ذخیره‌شده نمایندهٔ ساعت محلی ایران است، پس weekday/time خودِ رکورد
    ملاک است.
    """
    windows = db.scalars(
        select(CounselorAvailability).where(
            CounselorAvailability.counselor_id == counselor_id,
            CounselorAvailability.is_active.is_(True),
        )
    ).all()
    if not windows:
        return None
    dt = scheduled_at
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)  # زمان دیواری ثبت‌شده (قرارداد سامانه)
    weekday = dt.weekday()
    t = dt.time()
    for w in windows:
        if w.weekday == weekday and w.start_time <= t < w.end_time:
            return None
    from app.api.v1.counselors import PERSIAN_WEEKDAYS

    day_names = "، ".join(sorted({PERSIAN_WEEKDAYS.get(w.weekday, str(w.weekday)) for w in windows}))
    return (
        "زمان انتخاب‌شده در روزها و ساعت‌های مشاورهٔ این مشاور نیست. "
        f"بازه‌های اعلام‌شدهٔ مشاور: {day_names} "
        "(" + "، ".join(f"{w.start_time.strftime('%H:%M')} تا {w.end_time.strftime('%H:%M')}" for w in windows) + ")"
    )


def _can_access_case(db: Session, actor, case: Case) -> bool:
    roles = _roles(actor)
    if roles & set(STAFF_ROLES):
        return True
    if "COUNSELOR" in roles:
        c = db.scalar(select(Counselor).where(Counselor.user_id == actor.id))
        if c is not None and counselor_can_access(db, c.id, case):
            return True
    return False


def _appt_out(db: Session, a: Appointment) -> dict:
    case = db.get(Case, a.case_id)
    applicant = db.get(Applicant, case.applicant_id) if case else None
    c = db.get(Counselor, a.counselor_id)
    service = db.get(Service, a.service_id) if a.service_id else None
    return {
        "id": str(a.id),
        "case_id": str(a.case_id),
        "case_number": case.case_number if case else None,
        "applicant_name": (f"{applicant.first_name} {applicant.last_name}" if applicant else None),
        "counselor_name": (f"{c.first_name} {c.last_name}" if c else None),
        "scheduled_at": a.scheduled_at.isoformat(),
        "duration_minutes": a.duration_minutes,
        "location": a.location,
        "status": a.status,
        "note": a.note,
        # فاز ۲۸ - B06/B07: خدمت + snapshot قیمت (تغییر تعرفه اثر ندارد)
        "service_id": str(a.service_id) if a.service_id else None,
        "service_title": service.title if service else None,
        "tariff_version_id": str(a.tariff_version_id) if a.tariff_version_id else None,
        "price_amount": float(a.price_amount) if a.price_amount is not None else None,
        "price_currency": a.price_currency,
    }


@router.get("/appointments")
def list_appointments(
    case_id: uuid.UUID | None = Query(default=None),
    status: str = Query(default="", max_length=20),
    page: int = Query(default=1, ge=1, le=1_000_000),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    actor=Depends(get_current_user),
) -> dict:
    roles = _roles(actor)
    if not (roles & set(VIEW_ROLES)):
        raise HTTPException(status_code=403, detail="دسترسی مجاز نیست")
    q = select(Appointment)
    is_staff = bool(roles & set(STAFF_ROLES))
    if not is_staff:
        c = db.scalar(select(Counselor).where(Counselor.user_id == actor.id))
        if c is None:
            return {"items": [], "total": 0, "page": page, "page_size": page_size}
        q = q.where(Appointment.counselor_id == c.id)
    if case_id is not None:
        q = q.where(Appointment.case_id == case_id)
    if status in ("scheduled", "done", "cancelled", "no_show"):
        q = q.where(Appointment.status == status)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    items = db.scalars(
        q.order_by(Appointment.scheduled_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {"items": [_appt_out(db, a) for a in items], "total": total, "page": page, "page_size": page_size}


@router.post("/appointments", status_code=201)
def create_appointment(payload: AppointmentCreate, db: Session = Depends(get_db), actor=Depends(get_current_user)) -> dict:
    case = db.get(Case, payload.case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="پرونده یافت نشد")
    if not _can_access_case(db, actor, case):
        raise HTTPException(status_code=404, detail="پرونده یافت نشد")
    if case.status in (CaseStatus.CLOSED, CaseStatus.ARCHIVED):
        raise HTTPException(status_code=409, detail="برای پرونده بسته یا بایگانی نمی‌توان نوبت ثبت کرد")

    counselor_id = payload.counselor_id or case.primary_counselor_id
    if counselor_id is None:
        raise HTTPException(status_code=422, detail="ابتدا مشاور اصلی پرونده را تخصیص دهید")
    counselor = db.get(Counselor, counselor_id)
    if counselor is None or counselor.status != "active":
        raise HTTPException(status_code=422, detail="مشاور یافت نشد یا فعال نیست")

    # فاز ۷۴: زمان نوبت باید در روزها/ساعت‌های مشاورهٔ تعیین‌شدهٔ مشاور باشد
    conflict = availability_conflict(db, counselor_id, payload.scheduled_at)
    if conflict is not None:
        raise HTTPException(status_code=422, detail=conflict)

    # فاز ۲۸ - B06: خدمت انتخابی باید فعال باشد؛ مدت پیش‌فرض از خدمت
    # فاز ۲۸ - B07: snapshot قیمت از تعرفه معتبر در تاریخ نوبت
    service = None
    if payload.service_id is not None:
        service = db.get(Service, payload.service_id)
        if service is None:
            raise HTTPException(status_code=404, detail="خدمت یافت نشد")
        if service.status != ServiceStatus.ACTIVE:
            raise HTTPException(status_code=409, detail="این خدمت غیرفعال است و رزرو جدید نمی‌پذیرد")

    duration = payload.duration_minutes
    if service is not None and duration is None:
        duration = service.duration_minutes

    from app.api.v1.catalog import current_tariff

    tariff = current_tariff(db, service.id, payload.scheduled_at.date()) if service is not None else None

    a = Appointment(
        case_id=case.id,
        counselor_id=counselor_id,
        scheduled_at=payload.scheduled_at,
        duration_minutes=duration,
        location=payload.location,
        note=payload.note,
        service_id=service.id if service is not None else None,
        tariff_version_id=tariff.id if tariff is not None else None,
        price_amount=tariff.amount if tariff is not None else None,
        price_currency=tariff.currency if tariff is not None else None,
        created_by=actor.id,
    )
    db.add(a)
    db.commit()
    record_audit(db, action="appointment.created", actor_user_id=actor.id,
                 entity_type="appointment", entity_id=str(a.id),
                 detail={"service_id": str(service.id) if service is not None else None,
                         "tariff_snapshot": float(tariff.amount) if tariff is not None else None})
    return _appt_out(db, a)


@router.patch("/appointments/{appointment_id}")
def update_appointment(
    appointment_id: uuid.UUID,
    payload: AppointmentUpdate,
    db: Session = Depends(get_db),
    actor=Depends(get_current_user),
) -> dict:
    a = db.get(Appointment, appointment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="نوبت یافت نشد")
    case = db.get(Case, a.case_id)
    if not _can_access_case(db, actor, case):
        raise HTTPException(status_code=404, detail="نوبت یافت نشد")

    changed: list[str] = []
    if payload.scheduled_at is not None:
        if a.status != AppointmentStatus.SCHEDULED:
            raise HTTPException(status_code=409, detail="فقط نوبت برنامه‌ریزی‌شده قابل جابه‌جایی است")
        # فاز ۷۴: زمان جدید هم باید در بازه‌های مشاور باشد
        conflict = availability_conflict(db, a.counselor_id, payload.scheduled_at)
        if conflict is not None:
            raise HTTPException(status_code=422, detail=conflict)
        a.scheduled_at = payload.scheduled_at
        changed.append("scheduled_at")
    if payload.duration_minutes is not None and a.status == AppointmentStatus.SCHEDULED:
        a.duration_minutes = payload.duration_minutes
        changed.append("duration")
    if payload.location is not None and a.status == AppointmentStatus.SCHEDULED:
        a.location = payload.location
        changed.append("location")
    if payload.note is not None:
        a.note = payload.note
        changed.append("note")
    if payload.status is not None and payload.status != a.status:
        if a.status != AppointmentStatus.SCHEDULED:
            raise HTTPException(status_code=409, detail="وضعیت این نوبت نهایی شده و قابل تغییر نیست")
        a.status = payload.status
        changed.append(f"status:{payload.status}")
    db.commit()
    record_audit(db, action="appointment.updated", actor_user_id=actor.id,
                 entity_type="appointment", entity_id=str(a.id), detail={"changed": changed})
    return _appt_out(db, a)


@router.get("/worklists/counselor-appointments")
def counselor_appointments(db: Session = Depends(get_db), actor=Depends(require_roles("COUNSELOR"))) -> dict:
    """کارتابل مشاور - نوبت‌های امروز و آینده (بند ۹.۱)"""
    c = db.scalar(select(Counselor).where(Counselor.user_id == actor.id))
    if c is None:
        return {"items": []}
    today_start = datetime.combine(
        datetime.now(timezone.utc).date(), time.min, tzinfo=timezone.utc
    )
    rows = db.execute(
        select(Appointment, Case, Applicant)
        .join(Case, Appointment.case_id == Case.id)
        .join(Applicant, Case.applicant_id == Applicant.id)
        .where(
            Appointment.counselor_id == c.id,
            Appointment.status == AppointmentStatus.SCHEDULED,
            Appointment.scheduled_at >= today_start,
        )
        .order_by(Appointment.scheduled_at)
        .limit(50)
    ).all()
    items = [{
        "id": str(a.id),
        "case_id": str(cs.id),
        "case_number": cs.case_number,
        "applicant_name": f"{ap.first_name} {ap.last_name}",
        "scheduled_at": a.scheduled_at.isoformat(),
        "duration_minutes": a.duration_minutes,
        "location": a.location,
    } for a, cs, ap in rows]
    return {"items": items}
