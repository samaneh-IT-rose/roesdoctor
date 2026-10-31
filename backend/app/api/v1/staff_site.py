"""عملیات پنلی مرتبط با سایت عمومی — فاز ۱۰"""
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.consultation import ConsultationRequest
from app.models.people import Counselor
from app.models.user import User
from app.services.audit import record_audit
from app.models.case import Case, CaseAssignment, CaseStatus
from app.models.people import Applicant
from app.api.v1.cases import generate_case_number
from datetime import date as date_type
from app.models.appointment import Appointment
from datetime import datetime as rdt, timezone as rtz
from app.services.case_access import counselor_can_access

router = APIRouter(tags=["site-ops"])

PHOTO_MAX = 2 * 1024 * 1024


def _detect_image(data: bytes) -> str | None:
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:4] == b"\x89PNG":
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


@router.post("/counselors/{counselor_id}/photo", status_code=201)
async def upload_counselor_photo(
    counselor_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor=Depends(require_roles("ORG_MANAGER", "SYSTEM_ADMIN")),
) -> dict:
    c = db.get(Counselor, counselor_id)
    if c is None:
        raise HTTPException(status_code=404, detail="مشاور یافت نشد")
    data = await file.read()
    if len(data) > PHOTO_MAX:
        raise HTTPException(status_code=422, detail="حجم عکس باید کمتر از ۲ مگابایت باشد")
    ext = _detect_image(data)
    if ext is None:
        raise HTTPException(status_code=422, detail="فقط تصویر JPEG/PNG/WebP پذیرفته می‌شود")

    folder = Path("uploads") / "counselor_photos"
    folder.mkdir(parents=True, exist_ok=True)
    fname = f"{uuid.uuid4().hex}.{ext}"
    (folder / fname).write_bytes(data)

    # حذف عکس قبلی (best-effort)
    if c.photo_path:
        old = Path("uploads") / c.photo_path
        try:
            if old.is_file():
                old.unlink()
        except OSError:
            pass

    c.photo_path = f"counselor_photos/{fname}"
    db.commit()
    record_audit(db, action="counselor.photo_uploaded", actor_user_id=actor.id,
                 entity_type="counselor", entity_id=str(c.id))
    return {"photo_url": f"/api/v1/public/counselors/{c.id}/photo"}


class ConsultStatusUpdate(BaseModel):
    status: str = Field(pattern="^(new|in_review|converted|archived)$")
    reception_note: str | None = Field(default=None, max_length=2000)
    add_contact_attempt: bool = False


def _out(db: Session, r: ConsultationRequest) -> dict:
    handler = db.get(User, r.handled_by) if r.handled_by else None
    return {
        "id": str(r.id),
        "full_name": r.full_name,
        "mobile": r.mobile,
        "topic": r.topic,
        "preferred_date": r.preferred_date.isoformat() if r.preferred_date else None,
        "preferred_slot": r.preferred_slot,
        "message": r.message,
        "status": r.status,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "handled_by_name": handler.display_name if handler else None,
        "reception_note": r.reception_note,
        "contact_attempts": r.contact_attempts or 0,
        "city": r.city,
        "referral_source": r.referral_source,
        "preferred_counselor_id": str(r.preferred_counselor_id) if r.preferred_counselor_id else None,
        "preferred_start_at": r.preferred_start_at.isoformat() if r.preferred_start_at else None,
        # فاز ۶۹: وضعیت پرداخت آنلاین رزرو (زرین‌پال) برای پذیرش
        "payment_status": r.payment_status,
        "paid_at": r.paid_at.isoformat() if r.paid_at else None,
    }


@router.get("/consultation-requests")
def list_consultation_requests(
    status: str = Query(default="", max_length=20),
    page: int = Query(default=1, ge=1, le=1_000_000),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _actor=Depends(require_roles("ORG_MANAGER", "RECEPTION", "SYSTEM_ADMIN", "COUNSELOR")),
) -> dict:
    q = select(ConsultationRequest)
    if status in ("new", "in_review", "converted", "archived"):
        q = q.where(ConsultationRequest.status == status)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    items = db.scalars(
        q.order_by(ConsultationRequest.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {"items": [_out(db, r) for r in items], "total": total, "page": page, "page_size": page_size}


@router.patch("/consultation-requests/{request_id}")
def update_consultation_request(
    request_id: uuid.UUID,
    payload: ConsultStatusUpdate,
    db: Session = Depends(get_db),
    actor=Depends(require_roles("ORG_MANAGER", "RECEPTION")),
) -> dict:
    r = db.get(ConsultationRequest, request_id)
    if r is None:
        raise HTTPException(status_code=404, detail="درخواست یافت نشد")
    r.status = payload.status
    if payload.reception_note is not None:
        r.reception_note = payload.reception_note
    if payload.add_contact_attempt:
        r.contact_attempts = (r.contact_attempts or 0) + 1
    r.handled_by = actor.id
    r.handled_at = datetime.now(timezone.utc)
    db.commit()
    record_audit(db, action="consultation.status_changed", actor_user_id=actor.id,
                 entity_type="consultation_request", entity_id=str(r.id),
                 detail={"status": payload.status})
    return _out(db, r)


class ConvertRequest(BaseModel):
    create_case: bool = False
    counselor_id: uuid.UUID | None = None
    service_location_id: uuid.UUID | None = None
    first_appointment_at: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$")


@router.post("/consultation-requests/{request_id}/convert")
def convert_request(request_id: uuid.UUID, payload: ConvertRequest, db: Session = Depends(get_db), actor=Depends(get_current_user)) -> dict:
    r = db.get(ConsultationRequest, request_id)
    if r is None:
        raise HTTPException(status_code=404, detail="درخواست یافت نشد")
    # ماتریس: مدیر سازمان/پذیرش همیشه؛ مشاور تنها اگر به‌عنوان همکار/اصلی به یکی از پرونده‌های متقاضی تخصیص دارد
    actor_roles = {rc.code for rc in actor.roles}
    if not (actor_roles & {"ORG_MANAGER", "RECEPTION"}):
        if "COUNSELOR" not in actor_roles:
            raise HTTPException(status_code=403, detail="دسترسی مجاز نیست")
        counselor = db.scalar(select(Counselor).where(Counselor.user_id == actor.id))
        if counselor is None or payload.counselor_id != counselor.id:
            raise HTTPException(status_code=403, detail="مشاور فقط می‌تواند درخواست را با خودش به‌عنوان مشاور تبدیل کند")
    if r.status not in ("new", "in_review"):
        raise HTTPException(status_code=409, detail="این درخواست قبلاً تبدیل یا بایگانی شده است")

    full_name = (r.full_name or "").strip()
    parts = full_name.split(" ", 1)
    first = parts[0] if parts else full_name
    last = parts[1] if len(parts) > 1 else "—"

    applicant = db.scalar(select(Applicant).where(Applicant.mobile == r.mobile))
    created_applicant = False
    if applicant is None:
        applicant = Applicant(
            first_name=first, last_name=last, mobile=r.mobile,
            status="active", record_source="manual",
        )
        db.add(applicant)
        db.flush()
        created_applicant = True

    case_id = None
    case_number = None
    appt_created = False
    if payload.create_case:
        counselor_id = payload.counselor_id
        if counselor_id is not None:
            cc = db.get(Counselor, counselor_id)
            if cc is None or cc.status != "active":
                raise HTTPException(status_code=422, detail="مشاور انتخاب‌شده فعال نیست")
        case = Case(
            case_number=generate_case_number(db),
            applicant_id=applicant.id,
            acceptance_date=date_type.today(),
            service_location_id=payload.service_location_id,
            service_type=r.topic,
            created_by=actor.id,
        )
        db.add(case)
        db.flush()
        if counselor_id is not None:
            db.add(CaseAssignment(
                case_id=case.id, counselor_id=counselor_id,
                reason="تبدیل از درخواست مشاوره سایت", assigned_by=actor.id, role_in_case="primary",
            ))
            case.primary_counselor_id = counselor_id
            case.status = CaseStatus.ACTIVE
        else:
            case.status = CaseStatus.AWAITING_ASSIGNMENT
        case_id = case.id
        case_number = case.case_number
        if payload.first_appointment_at:
            if counselor_id is None:
                raise HTTPException(status_code=422, detail="برای ثبت نوبت اولیه، انتخاب مشاور الزامی است")
            try:
                appt_at = rdt.fromisoformat(payload.first_appointment_at).replace(tzinfo=rtz.utc)
            except ValueError:
                raise HTTPException(status_code=422, detail="زمان نوبت اولیه نامعتبر است")
            db.add(Appointment(
                case_id=case.id, counselor_id=counselor_id,
                scheduled_at=appt_at, status="scheduled",
                note="نوبت اولیه — تبدیل از درخواست سایت", created_by=actor.id,
            ))
            appt_created = True

    r.status = "converted"
    r.applicant_id = applicant.id
    r.case_id = case_id
    r.handled_by = actor.id
    from datetime import datetime as dt, timezone as tz
    r.handled_at = dt.now(tz.utc)
    db.commit()
    record_audit(db, action="consultation.converted", actor_user_id=actor.id,
                 entity_type="consultation_request", entity_id=str(r.id),
                 detail={"applicant_id": str(applicant.id), "case_id": str(case_id) if case_id else None})
    return {
        "status": "converted",
        "applicant_id": str(applicant.id),
        "applicant_created": created_applicant,
        "case_id": str(case_id) if case_id else None,
        "case_number": case_number,
        "first_appointment_created": appt_created,
    }

class ManualConsultationCreate(BaseModel):
    full_name: str = Field(min_length=3, max_length=200)
    mobile: str = Field(min_length=10, max_length=20)
    topic: str = Field(min_length=2, max_length=100)
    preferred_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    preferred_slot: str | None = Field(default=None, max_length=30)
    city: str | None = Field(default=None, max_length=100)
    referral_source: str | None = Field(default=None, max_length=200)
    message: str | None = Field(default=None, max_length=2000)
    reception_note: str | None = Field(default=None, max_length=2000)


def _normalize_mobile_staff(raw: str) -> str:
    s = (raw or "").strip()
    for ch in (" ", "-", "(", ")"):
        s = s.replace(ch, "")
    if s.startswith("+98"):
        s = "0" + s[3:]
    elif s.startswith("98") and len(s) == 12:
        s = "0" + s[2:]
    return s


@router.post("/consultation-requests", status_code=201)
def create_consultation_request(payload: ManualConsultationCreate, db: Session = Depends(get_db), actor=Depends(require_roles("ORG_MANAGER", "RECEPTION", "COUNSELOR"))) -> dict:
    """ثبت حضوری/تلفنی درخواست مشاوره توسط کارکنان (بند ۹.۱ سند)"""
    mobile = _normalize_mobile_staff(payload.mobile)
    if not re.fullmatch(r"09\d{9}", mobile):
        raise HTTPException(status_code=422, detail="شماره موبایل معتبر نیست (نمونه: 09121234567)")
    preferred = None
    if payload.preferred_date:
        try:
            preferred = date_type.fromisoformat(payload.preferred_date)
        except ValueError:
            raise HTTPException(status_code=422, detail="تاریخ نامعتبر است")
    r = ConsultationRequest(
        full_name=payload.full_name.strip(),
        mobile=mobile,
        topic=payload.topic.strip(),
        preferred_date=preferred,
        preferred_slot=payload.preferred_slot,
        message=payload.message,
        city=payload.city,
        referral_source=payload.referral_source or "ثبت در پنل",
        reception_note=payload.reception_note,
        status="in_review",
    )
    db.add(r)
    db.commit()
    record_audit(db, action="consultation.created_by_staff", actor_user_id=actor.id,
                 entity_type="consultation_request", entity_id=str(r.id))
    return {
        "id": str(r.id),
        "full_name": r.full_name,
        "mobile": r.mobile,
        "status": r.status,
    }
