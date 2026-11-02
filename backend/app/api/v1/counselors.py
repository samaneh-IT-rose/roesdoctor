import uuid
from datetime import date, time as dtime

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.catalog import (
    CounselorCredential,
    CredentialKind,
    CredentialVerificationStatus,
)
from app.models.branch import Branch
from app.models.location import Province
from app.models.people import Counselor, CounselorAvailability, ServiceLocation
from app.models.user import Role, User, UserStatus
from app.schemas.people import CounselorCreate, CounselorUpdate
from app.services import counselor_import as ci
from app.services.audit import record_audit
from app.services.qualification import is_counselor_bookable

router = APIRouter(prefix="/counselors", tags=["counselors"])

VIEW_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER", "TECHNICAL_SUPERVISOR")
MANAGE_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER")


def _out(c: Counselor, db: Session) -> dict:
    loc_title = None
    if c.service_location_id:
        loc = db.get(ServiceLocation, c.service_location_id)
        loc_title = loc.title if loc else None
    # فاز ۶۴: نام استان از جدول پایه
    province_name = None
    if c.province_code:
        prov = db.scalar(select(Province).where(Province.code == c.province_code))
        province_name = prov.name if prov else None
    # فاز ۶۵: کلینک محل خدمت (انتقال از رز هاب) + شعبهٔ متناظر (فاز ۶۶)
    branch_title = None
    if c.branch_id:
        branch = db.get(Branch, c.branch_id)
        branch_title = branch.name if branch else None
    # فاز ۲۸ - B05: وضعیت صلاحیت برای فهرست قابل رزرو
    bookable = is_counselor_bookable(db, c)
    approved_count = db.scalar(
        select(func.count()).select_from(CounselorCredential).where(
            CounselorCredential.counselor_id == c.id,
            CounselorCredential.verification_status == CredentialVerificationStatus.APPROVED,
        )
    ) or 0
    pending_count = db.scalar(
        select(func.count()).select_from(CounselorCredential).where(
            CounselorCredential.counselor_id == c.id,
            CounselorCredential.verification_status == CredentialVerificationStatus.PENDING,
        )
    ) or 0
    return {
        "id": str(c.id),
        "counselor_code": c.counselor_code,
        "first_name": c.first_name,
        "last_name": c.last_name,
        "national_id": c.national_id,
        "professional_title": c.professional_title,
        "degree": c.degree,
        "specialty": c.specialty,
        "license_number": c.license_number,
        "license_expiry_date": c.license_expiry_date.isoformat() if c.license_expiry_date else None,
        "license_verified": c.license_verified,
        "work_mobile": c.work_mobile,
        "email": c.email,
        "capacity": c.capacity,
        "service_location_title": loc_title,
        "province_code": c.province_code,
        "province_name": province_name,
        "clinic": c.clinic,
        "branch_title": branch_title,
        "professional_rank": c.professional_rank,
        "contract_number": c.contract_number,
        "sheba_number": c.sheba_number,
        "detailed_code": c.detailed_code,
        "status": c.status,
        "has_account": c.user_id is not None,
        "bookable": bookable,
        "approved_credentials": approved_count,
        "pending_credentials": pending_count,
    }


@router.get("")
def list_counselors(
    search: str = Query(default="", max_length=100),
    page: int = Query(default=1, ge=1, le=1_000_000),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _actor=Depends(require_roles(*VIEW_ROLES)),
) -> dict:
    q = select(Counselor)
    if search.strip():
        like = f"%{search.strip()}%"
        q = q.where(or_(Counselor.counselor_code.ilike(like), Counselor.first_name.ilike(like), Counselor.last_name.ilike(like)))
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    items = db.scalars(q.order_by(Counselor.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [_out(c, db) for c in items], "total": total, "page": page, "page_size": page_size}


def _validate_province(db: Session, code: str | None) -> None:
    """فاز ۶۴: اگر کد استان داده شده باشد باید در جدول پایه باشد."""
    if code and db.scalar(select(Province).where(Province.code == code)) is None:
        raise HTTPException(status_code=422, detail="کد استان معتبر نیست (۰۱ تا ۳۱)")


@router.post("", status_code=201)
def create_counselor(payload: CounselorCreate, db: Session = Depends(get_db), actor=Depends(require_roles(*MANAGE_ROLES))) -> dict:
    code = payload.counselor_code.strip()
    if db.scalar(select(Counselor).where(Counselor.counselor_code == code)):
        raise HTTPException(status_code=409, detail="این کد مشاور قبلاً ثبت شده است")
    if payload.national_id and db.scalar(select(Counselor).where(Counselor.national_id == payload.national_id)):
        raise HTTPException(status_code=409, detail="این کد ملی قبلاً ثبت شده است")
    if payload.service_location_id and db.get(ServiceLocation, payload.service_location_id) is None:
        raise HTTPException(status_code=422, detail="محل خدمت نامعتبر است")
    _validate_province(db, payload.province_code)

    c = Counselor(
        counselor_code=code,
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        national_id=payload.national_id or None,
        professional_title=payload.professional_title,
        degree=payload.degree,
        specialty=payload.specialty,
        license_number=payload.license_number,
        license_expiry_date=payload.license_expiry_date,
        work_mobile=payload.work_mobile,
        email=payload.email,
        service_location_id=payload.service_location_id,
        capacity=payload.capacity,
        province_code=payload.province_code or None,
        professional_rank=payload.professional_rank or None,
        contract_number=payload.contract_number or None,
        sheba_number=payload.sheba_number or None,
        detailed_code=payload.detailed_code or None,
        status="active",
    )
    db.add(c)
    db.flush()
    if payload.create_account:
        if not payload.username:
            raise HTTPException(status_code=422, detail="برای ایجاد حساب، نام کاربری الزامی است")
        uname = payload.username.strip().lower()
        if db.scalar(select(User).where(User.username == uname)):
            raise HTTPException(status_code=409, detail="نام کاربری قبلاً ثبت شده است")
        u = User(username=uname, display_name=f"{c.first_name} {c.last_name}", status=UserStatus.PENDING, must_change_password=True)
        u.roles.append(db.get(Role, "COUNSELOR"))
        db.add(u)
        db.flush()
        c.user_id = u.id
    db.commit()
    record_audit(db, action="counselor.created", actor_user_id=actor.id, entity_type="counselor", entity_id=str(c.id))
    return _out(c, db)


# ---------------- فاز ۶۴ - ورود گروهی مشاوران از فایل اکسل شرکت رز ----------------

@router.get("/import-template")
def download_import_template(
    db: Session = Depends(get_db),
    _actor=Depends(require_roles(*MANAGE_ROLES)),
):
    """دانلود قالب اکسل ورود مشاوران (همان ستون‌های فایل «اسامی مشاورین»)."""
    data = ci.build_template()
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="rosepsy-counselors-import-template.xlsx"'},
    )


@router.post("/import")
async def import_counselors(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor=Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    """بارگذاری فایل اکسل مشاوران؛ کلید یکتایی کد ملی است.

    مشاور جدید: ایجاد + حساب فعال (نام کاربری = کد ملی، رمز اولیه = شماره تماس).
    مشاور موجود: به‌روزرسانی اطلاعات. ردیف‌های خطادار پردازش نمی‌شوند و بقیه
    ردیف‌ها ادامه می‌یابند (خلاصه و خطای هر ردیف در پاسخ برمی‌گردد).
    """
    data = await file.read()
    rows, file_error = ci.parse_file(data)
    if file_error:
        raise HTTPException(status_code=422, detail=file_error)
    if not rows:
        raise HTTPException(status_code=422, detail="ردیف داده‌ای در فایل یافت نشد")
    return ci.validate_and_upsert(db, rows, actor, upload_name=file.filename)


@router.get("/{counselor_id}")
def get_counselor(counselor_id: uuid.UUID, db: Session = Depends(get_db), _actor=Depends(require_roles(*VIEW_ROLES))) -> dict:
    c = db.get(Counselor, counselor_id)
    if c is None:
        raise HTTPException(status_code=404, detail="مشاور یافت نشد")
    return _out(c, db)


@router.patch("/{counselor_id}")
def update_counselor(counselor_id: uuid.UUID, payload: CounselorUpdate, db: Session = Depends(get_db), actor=Depends(require_roles(*MANAGE_ROLES))) -> dict:
    c = db.get(Counselor, counselor_id)
    if c is None:
        raise HTTPException(status_code=404, detail="مشاور یافت نشد")
    changed: list[str] = []
    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"] is not None:
        if data["status"] not in ("active", "inactive", "suspended"):
            raise HTTPException(status_code=422, detail="وضعیت نامعتبر است")
        c.status = data["status"]
        changed.append("status")
    if data.get("province_code") is not None:
        _validate_province(db, data["province_code"])
    for f in ("professional_title", "degree", "specialty", "license_number", "work_mobile", "email", "capacity", "license_expiry_date", "service_location_id",
              "province_code", "professional_rank", "contract_number", "sheba_number", "detailed_code"):
        if f in data and data[f] is not None:
            setattr(c, f, data[f])
            changed.append(f)
    db.commit()
    record_audit(db, action="counselor.updated", actor_user_id=actor.id, entity_type="counselor", entity_id=str(c.id), detail={"changed": changed})
    return _out(c, db)


# ---------------- فاز ۲۸ - B05: مدارک و صلاحیت مشاور ----------------

class CredentialCreate(BaseModel):
    kind: str = Field(default=CredentialKind.LICENSE, max_length=50)
    title: str = Field(min_length=2, max_length=200)
    license_number: str | None = Field(default=None, max_length=100)
    issued_at: date | None = None
    expires_at: date | None = None
    file_path: str | None = Field(default=None, max_length=255)


def _cred_out(c: CounselorCredential) -> dict:
    return {
        "id": str(c.id),
        "counselor_id": str(c.counselor_id),
        "kind": c.kind,
        "title": c.title,
        "license_number": c.license_number,
        "issued_at": c.issued_at.isoformat() if c.issued_at else None,
        "expires_at": c.expires_at.isoformat() if c.expires_at else None,
        "file_path": c.file_path,
        "verification_status": c.verification_status,
        "reviewed_at": c.reviewed_at.isoformat() if c.reviewed_at else None,
        "review_note": c.review_note,
    }


@router.get("/{counselor_id}/credentials")
def list_credentials(counselor_id: uuid.UUID, db: Session = Depends(get_db), _actor=Depends(require_roles(*VIEW_ROLES))) -> dict:
    c = db.get(Counselor, counselor_id)
    if c is None:
        raise HTTPException(status_code=404, detail="مشاور یافت نشد")
    items = db.scalars(
        select(CounselorCredential)
        .where(CounselorCredential.counselor_id == counselor_id)
        .order_by(CounselorCredential.created_at.desc())
    ).all()
    return {"items": [_cred_out(x) for x in items], "total": len(items)}


@router.post("/{counselor_id}/credentials", status_code=201)
def add_credential(counselor_id: uuid.UUID, payload: CredentialCreate, db: Session = Depends(get_db), actor=Depends(require_roles(*MANAGE_ROLES))) -> dict:
    c = db.get(Counselor, counselor_id)
    if c is None:
        raise HTTPException(status_code=404, detail="مشاور یافت نشد")
    if payload.kind not in CredentialKind.ALL:
        raise HTTPException(status_code=422, detail="نوع مدرک نامعتبر است")
    if payload.expires_at and payload.issued_at and payload.expires_at < payload.issued_at:
        raise HTTPException(status_code=422, detail="تاریخ انقضا نمی‌تواند قبل از تاریخ صدور باشد")
    cred = CounselorCredential(
        counselor_id=counselor_id,
        kind=payload.kind,
        title=payload.title.strip(),
        license_number=payload.license_number,
        issued_at=payload.issued_at,
        expires_at=payload.expires_at,
        file_path=payload.file_path,
        verification_status=CredentialVerificationStatus.PENDING,
    )
    db.add(cred)
    db.commit()
    record_audit(db, action="credential.created", actor_user_id=actor.id,
                 entity_type="counselor_credential", entity_id=str(cred.id),
                 detail={"counselor_id": str(counselor_id), "kind": cred.kind})
    return _cred_out(cred)

# ---------------------------------------------------------------------------
# فاز ۷۴ — روزها و ساعت‌های مشاورهٔ هر مشاور
# مشاور در کارتابل خودش (/worklist) بازه‌های هفتگی‌اش را تعریف می‌کند و
# نوبت‌دهی/رزرو آنلاین فقط در همین بازه‌ها پذیرفته می‌شود.
# ---------------------------------------------------------------------------
PERSIAN_WEEKDAYS: dict[int, str] = {
    5: "شنبه", 6: "یکشنبه", 0: "دوشنبه", 1: "سه‌شنبه",
    2: "چهارشنبه", 3: "پنجشنبه", 4: "جمعه",
}


class AvailabilityWindow(BaseModel):
    weekday: int = Field(ge=0, le=6)
    start_time: str = Field(min_length=4, max_length=5)  # "HH:MM"
    end_time: str = Field(min_length=4, max_length=5)  # "HH:MM"
    is_active: bool = True


class AvailabilitySet(BaseModel):
    items: list[AvailabilityWindow] = Field(default_factory=list)


def _parse_hhmm(raw: str, what: str) -> dtime:
    try:
        hh, mm = raw.strip().split(":")
        return dtime(int(hh), int(mm))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=f"ساعت {what} نامعتبر است (قالب HH:MM)") from exc


def _availability_out(rows: list[CounselorAvailability]) -> dict:
    items = [
        {
            "id": str(r.id),
            "weekday": r.weekday,
            "weekday_name": PERSIAN_WEEKDAYS.get(r.weekday, str(r.weekday)),
            "start_time": r.start_time.strftime("%H:%M"),
            "end_time": r.end_time.strftime("%H:%M"),
            "is_active": bool(r.is_active),
        }
        for r in rows
    ]
    # ترتیب هفتهٔ ایرانی: شنبه … جمعه
    order = {5: 0, 6: 1, 0: 2, 1: 3, 2: 4, 3: 5, 4: 6}
    items.sort(key=lambda x: (order.get(x["weekday"], 9), x["start_time"]))
    return {"items": items}


def _counselor_of_user(db: Session, user) -> Counselor | None:
    return db.scalar(select(Counselor).where(Counselor.user_id == user.id))


@router.get("/me/availability")
def my_availability(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    """بازه‌های هفتگی مشاور جاری (کارتابل مشاور)."""
    c = _counselor_of_user(db, actor)
    if c is None:
        return {"items": [], "counselor_id": None, "configured": False}
    rows = db.scalars(
        select(CounselorAvailability)
        .where(CounselorAvailability.counselor_id == c.id)
        .order_by(CounselorAvailability.weekday, CounselorAvailability.start_time)
    ).all()
    return {**_availability_out(rows), "counselor_id": str(c.id), "configured": True}


@router.put("/me/availability")
def set_my_availability(
    payload: AvailabilitySet,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    """جایگزینی کامل بازه‌های هفتگی مشاور جاری."""
    c = _counselor_of_user(db, actor)
    if c is None:
        raise HTTPException(status_code=404, detail="پروندهٔ مشاور برای حساب شما یافت نشد")
    windows: list[tuple[int, dtime, dtime, bool]] = []
    seen: set[tuple[int, str]] = set()
    for w in payload.items:
        st = _parse_hhmm(w.start_time, "شروع")
        en = _parse_hhmm(w.end_time, "پایان")
        if en <= st:
            raise HTTPException(status_code=422, detail="ساعت پایان هر بازه باید بعد از ساعت شروع باشد")
        if w.weekday in seen:
            # چند بازه در یک روز مجاز است ولی همان ساعت شروع تکراری نیست
            pass
        key = (w.weekday, st.strftime("%H:%M"))
        if key in seen:
            raise HTTPException(status_code=409, detail="برای یک روز نمی‌توان دو بازه با ساعت شروع یکسان ثبت کرد")
        seen.add(key)
        windows.append((w.weekday, st, en, w.is_active))
    for row in db.scalars(
        select(CounselorAvailability).where(CounselorAvailability.counselor_id == c.id)
    ).all():
        db.delete(row)
    for weekday, st, en, active in windows:
        db.add(
            CounselorAvailability(
                counselor_id=c.id, weekday=weekday, start_time=st, end_time=en, is_active=active
            )
        )
    db.commit()
    record_audit(db, action="counselor.availability_updated", actor_user_id=actor.id,
                 entity_type="counselor", entity_id=str(c.id),
                 detail={"windows": len(windows)})
    rows = db.scalars(
        select(CounselorAvailability)
        .where(CounselorAvailability.counselor_id == c.id)
        .order_by(CounselorAvailability.weekday, CounselorAvailability.start_time)
    ).all()
    return {**_availability_out(rows), "counselor_id": str(c.id), "configured": True}


@router.get("/{counselor_id}/availability")
def counselor_availability(
    counselor_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles("SYSTEM_ADMIN", "ORG_MANAGER", "TECHNICAL_SUPERVISOR", "RECEPTION", "COUNSELOR")),
) -> dict:
    """بازه‌های هفتگی یک مشاور — برای پذیرش/مدیر هنگام ثبت نوبت."""
    c = db.get(Counselor, counselor_id)
    if c is None:
        raise HTTPException(status_code=404, detail="مشاور یافت نشد")
    rows = db.scalars(
        select(CounselorAvailability)
        .where(CounselorAvailability.counselor_id == c.id)
        .order_by(CounselorAvailability.weekday, CounselorAvailability.start_time)
    ).all()
    return {**_availability_out(rows), "counselor_id": str(c.id), "configured": bool(rows)}
