"""فاز ۲۹ - B31 سند جامع: مراکز مشاوره و شعب.

قواعد سند:
- slug یکتا؛ عرض جغرافیایی بین −۹۰ و ۹۰؛ طول بین −۱۸۰ و ۱۸۰؛
- شعبه منتشرنشده عمومی نیست؛
- «خدمت ناموجود برای شعبه نشان داده نشود» — خروجی عمومی فقط خدمتِ
  فعالِ offering فعالِ شعبه منتشرشده را برمی‌گرداند.

فاز ۳۲ - B40 + تصمیم D03: نقشه شعب با سرویس نقشه پلاگین‌پذیر
- /public/branches/nearby: مرتب‌سازی شعب با فاصله هاروساین از مختصات کاربر؛
  پذیرش سند: «مکان کاربر فقط برای مرتب‌سازی، ذخیره نمی‌شود» — مختصات کاربر
  در پایگاه‌داده نوشته نمی‌شود، در audit ثبت نمی‌شود و در پاسخ بازتاب
  نمی‌یابد (بدون لاگ).
- /public/map/config: متادیتای سرویس نقشه فعال (D03) — کلید سرویس نقشه
  هرگز به کلاینت ارسال نمی‌شود.
"""
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, get_db, require_roles
from app.models.branch import Branch, BranchServiceOffering, BranchStatus, Clinic
from app.models.catalog import Service
from app.models.user import User
from app.services.maps import active_map_provider, configured_map_providers, haversine_km

router = APIRouter(tags=["branches"])

MANAGE_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER")

_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,118}[a-z0-9])?$")


# ---------------------------------------------------------------- schemas
class ClinicCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    phone: str | None = Field(default=None, max_length=30)
    website: str | None = Field(default=None, max_length=200)
    is_active: bool = True


class ClinicUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    phone: str | None = Field(default=None, max_length=30)
    website: str | None = Field(default=None, max_length=200)
    is_active: bool | None = None


class BranchCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    province: str | None = Field(default=None, max_length=80)
    city: str | None = Field(default=None, max_length=80)
    address: str | None = Field(default=None, max_length=500)
    postal_code: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=30)
    working_hours: dict | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    status: str = Field(default=BranchStatus.DRAFT)
    service_ids: list[uuid.UUID] = Field(default_factory=list)


class BranchUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    province: str | None = Field(default=None, max_length=80)
    city: str | None = Field(default=None, max_length=80)
    address: str | None = Field(default=None, max_length=500)
    postal_code: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=30)
    working_hours: dict | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    status: str | None = None


class OfferingsUpdate(BaseModel):
    service_ids: list[uuid.UUID] = Field(default_factory=list)


# ---------------------------------------------------------------- helpers
def _branch_out(db: Session, b: Branch, with_services: bool = False) -> dict:
    data = {
        "id": str(b.id),
        "clinic_id": str(b.clinic_id),
        "name": b.name,
        "province": b.province,
        "city": b.city,
        "address": b.address,
        "postal_code": b.postal_code,
        "phone": b.phone,
        "working_hours": b.working_hours,
        "latitude": float(b.latitude) if b.latitude is not None else None,
        "longitude": float(b.longitude) if b.longitude is not None else None,
        "status": b.status,
        "created_at": b.created_at.isoformat() if b.created_at else None,
    }
    if with_services:
        rows = db.execute(
            select(BranchServiceOffering, Service)
            .join(Service, Service.id == BranchServiceOffering.service_id)
            .where(BranchServiceOffering.branch_id == b.id)
            .order_by(Service.title)
        ).all()
        data["services"] = [
            {
                "id": str(svc.id),
                "title": svc.title,
                "duration_minutes": svc.duration_minutes,
                "session_type": svc.session_type,
                "is_active": svc.status == "active" and off.is_active,
            }
            for off, svc in rows
        ]
    return data


def _clinic_out(db: Session, c: Clinic) -> dict:
    branch_count = len(
        db.scalars(select(Branch.id).where(Branch.clinic_id == c.id)).all()
    )
    return {
        "id": str(c.id),
        "name": c.name,
        "slug": c.slug,
        "description": c.description,
        "phone": c.phone,
        "website": c.website,
        "is_active": c.is_active,
        "branch_count": branch_count,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _validate_status(status: str | None) -> str | None:
    if status is not None and status not in BranchStatus.ALL:
        raise HTTPException(status_code=422, detail="وضعیت شعبه باید draft یا published باشد")
    return status


def _set_offerings(db: Session, branch: Branch, service_ids: list[uuid.UUID]) -> None:
    seen: set[uuid.UUID] = set()
    for sid in service_ids:
        if sid in seen:
            continue
        seen.add(sid)
        svc = db.get(Service, sid)
        if svc is None:
            raise HTTPException(status_code=404, detail=f"خدمت یافت نشد: {sid}")
        exists = db.scalars(
            select(BranchServiceOffering).where(
                BranchServiceOffering.branch_id == branch.id,
                BranchServiceOffering.service_id == sid,
            )
        ).first()
        if exists is None:
            db.add(BranchServiceOffering(branch_id=branch.id, service_id=sid, is_active=True))


# ---------------------------------------------------------------- clinics
@router.get("/clinics")
def list_clinics(
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES, "TECHNICAL_SUPERVISOR", "RECEPTION")),
) -> dict:
    clinics = db.scalars(select(Clinic).order_by(Clinic.name)).all()
    return {"items": [_clinic_out(db, c) for c in clinics]}


@router.post("/clinics", status_code=201)
def create_clinic(
    payload: ClinicCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    slug = payload.slug.strip().lower()
    if not _SLUG_RE.match(slug):
        raise HTTPException(status_code=422, detail="slug فقط حروف کوچک لاتین، عدد و خط تیره است")
    dup = db.scalars(select(Clinic.id).where(Clinic.slug == slug)).first()
    if dup is not None:
        raise HTTPException(status_code=409, detail="این slug قبلاً استفاده شده است")
    clinic = Clinic(
        name=payload.name.strip(),
        slug=slug,
        description=payload.description,
        phone=payload.phone,
        website=payload.website,
        is_active=payload.is_active,
        created_by=actor.id,
    )
    db.add(clinic)
    db.commit()
    db.refresh(clinic)
    return _clinic_out(db, clinic)


@router.patch("/clinics/{clinic_id}")
def update_clinic(
    clinic_id: uuid.UUID,
    payload: ClinicUpdate,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    clinic = db.get(Clinic, clinic_id)
    if clinic is None:
        raise HTTPException(status_code=404, detail="مرکز یافت نشد")
    for field in ("name", "description", "phone", "website"):
        value = getattr(payload, field)
        if value is not None:
            setattr(clinic, field, value)
    if payload.is_active is not None:
        clinic.is_active = payload.is_active
    db.commit()
    db.refresh(clinic)
    return _clinic_out(db, clinic)


# ---------------------------------------------------------------- branches
@router.get("/clinics/{clinic_id}/branches")
def list_branches(
    clinic_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES, "TECHNICAL_SUPERVISOR", "RECEPTION")),
) -> dict:
    branches = db.scalars(
        select(Branch).where(Branch.clinic_id == clinic_id).order_by(Branch.name)
    ).all()
    return {"items": [_branch_out(db, b) for b in branches]}


@router.post("/clinics/{clinic_id}/branches", status_code=201)
def create_branch(
    clinic_id: uuid.UUID,
    payload: BranchCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    clinic = db.get(Clinic, clinic_id)
    if clinic is None:
        raise HTTPException(status_code=404, detail="مرکز یافت نشد")
    status = _validate_status(payload.status)
    branch = Branch(
        clinic_id=clinic_id,
        name=payload.name.strip(),
        province=payload.province,
        city=payload.city,
        address=payload.address,
        postal_code=payload.postal_code,
        phone=payload.phone,
        working_hours=payload.working_hours,
        latitude=payload.latitude,
        longitude=payload.longitude,
        status=status or BranchStatus.DRAFT,
        created_by=actor.id,
    )
    db.add(branch)
    db.flush()
    _set_offerings(db, branch, payload.service_ids)
    db.commit()
    db.refresh(branch)
    return _branch_out(db, branch, with_services=True)


@router.patch("/branches/{branch_id}")
def update_branch(
    branch_id: uuid.UUID,
    payload: BranchUpdate,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    branch = db.get(Branch, branch_id)
    if branch is None:
        raise HTTPException(status_code=404, detail="شعبه یافت نشد")
    status = _validate_status(payload.status)
    for field in ("name", "province", "city", "address", "postal_code", "phone",
                  "working_hours", "latitude", "longitude"):
        value = getattr(payload, field)
        if value is not None:
            setattr(branch, field, value)
    if status is not None:
        branch.status = status
    db.commit()
    db.refresh(branch)
    return _branch_out(db, branch, with_services=True)


@router.put("/branches/{branch_id}/offerings")
def update_offerings(
    branch_id: uuid.UUID,
    payload: OfferingsUpdate,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    """تنظیم فهرست خدمات شعبه (مجموعه جایگزین کامل می‌شود)."""
    branch = db.get(Branch, branch_id)
    if branch is None:
        raise HTTPException(status_code=404, detail="شعبه یافت نشد")
    _set_offerings(db, branch, payload.service_ids)
    # حذف مواردی که دیگر در فهرست نیستند
    keep = set(payload.service_ids)
    for row in db.scalars(
        select(BranchServiceOffering).where(BranchServiceOffering.branch_id == branch_id)
    ).all():
        if row.service_id not in keep:
            db.delete(row)
    db.commit()
    return _branch_out(db, branch, with_services=True)


# ---------------------------------------------------------------- public
@router.get("/public/clinics")
def public_clinics(db: Session = Depends(get_db)) -> dict:
    clinics = db.scalars(
        select(Clinic).where(Clinic.is_active.is_(True)).order_by(Clinic.name)
    ).all()
    return {"items": [_clinic_out(db, c) for c in clinics]}


@router.get("/public/branches")
def public_branches(
    city: str | None = Query(default=None, max_length=80),
    service_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """فقط شعب منتشرشده؛ فیلتر شهر و خدمت؛ پذیرش سند: «خدمت ناموجود برای
    شعبه نشان داده نشود»."""
    q = (
        select(Branch)
        .options(joinedload(Branch.clinic))
        .where(Branch.status == BranchStatus.PUBLISHED)
    )
    if city:
        q = q.where(Branch.city == city.strip())
    if service_id is not None:
        q = q.join(
            BranchServiceOffering, BranchServiceOffering.branch_id == Branch.id
        ).where(
            BranchServiceOffering.service_id == service_id,
            BranchServiceOffering.is_active.is_(True),
        )
    branches = db.scalars(q.order_by(Branch.city, Branch.name)).unique().all()
    out = []
    for b in branches:
        item = _branch_out(db, b)
        item["clinic_name"] = b.clinic.name if b.clinic else None
        # خدمات عمومی: فقط خدمتِ فعالِ offering فعال
        rows = db.execute(
            select(BranchServiceOffering, Service)
            .join(Service, Service.id == BranchServiceOffering.service_id)
            .where(
                BranchServiceOffering.branch_id == b.id,
                BranchServiceOffering.is_active.is_(True),
                Service.status == "active",
            )
            .order_by(Service.title)
        ).all()
        item["services"] = [
            {"id": str(svc.id), "title": svc.title, "session_type": svc.session_type}
            for _off, svc in rows
        ]
        out.append(item)
    return {"items": out}


@router.get("/public/branches/nearby")
def public_branches_nearby(
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
    limit: int = Query(default=10, ge=1, le=50),
    city: str | None = Query(default=None, max_length=80),
    service_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """فاز ۳۲ - B40: شعب منتشرشده با مرتب‌سازی بر پایه فاصله (هاروساین).

    پذیرش سند: «مکان کاربر فقط برای مرتب‌سازی، ذخیره نمی‌شود» —
    مختصات کاربر (lat/lng) فقط پارامتر فراخوانی هستند؛ هیچ ردیفی در
    پایگاه‌داده نوشته نمی‌شود، هیچ رویداد audit با مختصات ثبت نمی‌شود و
    مختصات در پاسخ نیز بازتاب نمی‌یابد. فاقد مختصات در انتها می‌آیند.
    اگر lat/lng ناقص باشد، مرتب‌سازی نامی (مطابق /public/branches) است.
    """
    if (lat is None) != (lng is None):
        raise HTTPException(status_code=422, detail="هر دو مختصات lat و lng لازم است")
    q = (
        select(Branch)
        .options(joinedload(Branch.clinic))
        .where(Branch.status == BranchStatus.PUBLISHED)
    )
    if city:
        q = q.where(Branch.city == city.strip())
    if service_id is not None:
        q = q.join(
            BranchServiceOffering, BranchServiceOffering.branch_id == Branch.id
        ).where(
            BranchServiceOffering.service_id == service_id,
            BranchServiceOffering.is_active.is_(True),
        )
    branches = db.scalars(q.order_by(Branch.city, Branch.name)).unique().all()

    located: list[tuple[float, dict]] = []
    unlocated: list[dict] = []
    for b in branches:
        item = _branch_out(db, b)
        item["clinic_name"] = b.clinic.name if b.clinic else None
        rows = db.execute(
            select(BranchServiceOffering, Service)
            .join(Service, Service.id == BranchServiceOffering.service_id)
            .where(
                BranchServiceOffering.branch_id == b.id,
                BranchServiceOffering.is_active.is_(True),
                Service.status == "active",
            )
            .order_by(Service.title)
        ).all()
        item["services"] = [
            {"id": str(svc.id), "title": svc.title, "session_type": svc.session_type}
            for _off, svc in rows
        ]
        if lat is not None and lng is not None and b.latitude is not None and b.longitude is not None:
            # فاصله فقط در حافظه محاسبه و در پاسخ برمی‌گردد؛ هیچ‌جا ذخیره نمی‌شود
            item["distance_km"] = round(
                haversine_km(lat, lng, float(b.latitude), float(b.longitude)), 2
            )
            located.append((item["distance_km"], item))
        else:
            item["distance_km"] = None
            unlocated.append(item)

    if lat is not None:
        located.sort(key=lambda pair: pair[0])
        items = [item for _dist, item in located] + unlocated
        sorted_by = "distance"
    else:
        items = unlocated
        sorted_by = "name"
    return {
        "items": items[:limit],
        "total": len(items),
        "sorted_by": sorted_by,
        "privacy_note": "مکان کاربر فقط برای مرتب‌سازی استفاده شد و ذخیره نمی‌شود",
    }


@router.get("/public/map/config")
def public_map_config() -> dict:
    """فاز ۳۲ - D03: سرویس نقشه فعال برای رندر نقشه شعب در کلاینت.

    کلید سرویس‌های دارای کلید (نشنال/Map.ir) هرگز در پاسخ نیست؛
    برای آن‌ها tile_url صادر نمی‌شود و در تولید از SDK رسمی استفاده می‌شود.
    """
    provider = active_map_provider()
    return {
        "provider": provider,
        "providers": configured_map_providers(),
        "privacy_note": "مکان کاربر فقط برای مرتب‌سازی شعب استفاده می‌شود و ذخیره نمی‌شود",
    }


# ------------------------------------------------- فاز ۶۶ - نقشهٔ کلینیک‌های رز
@router.get("/public/clinics-map")
def public_clinics_map(db: Session = Depends(get_db)) -> dict:
    """نقشهٔ کلینیک‌های شرکت رز: شعب منتشرشده + مشاوران فعال هر شعبه.

    خروجی مستقیم برای صفحهٔ «کلینیک‌ها»ی سایت عمومی استفاده می‌شود؛
    هر آیتم شامل مشخصات کامل شعبه (نشانی، کدپستی، تلفن، مدیر، مسئول
    اجرایی، ساعات کاری، مختصات و لینک مسیریابی نشان) و فهرست مشاورانِ
    فعالِ همان کلینیک است.

    فاز ۶۷: موبایل و رتبهٔ مشاور از خروجی عمومی «حذف» شد (کسی نبیند —
    این داده‌ها فقط در پنل کارکنان دیده می‌شود)؛ در عوض پرچم ``bookable``
    هر مشاور برگردانده می‌شود تا فقط برای مشاورانِ واجد شرط B05 دکمهٔ
    «رزرو نوبت» در کارت کلینیک نمایش داده شود.
    """
    from datetime import date

    from app.models.catalog import CounselorCredential, CredentialVerificationStatus
    from app.models.location import Province
    from app.models.people import Counselor

    branches = db.scalars(
        select(Branch)
        .options(joinedload(Branch.clinic))
        .join(Clinic, Clinic.id == Branch.clinic_id)
        .where(
            Branch.status == BranchStatus.PUBLISHED,
            Clinic.is_active.is_(True),
        )
        .order_by(Branch.province_code.nulls_last(), Branch.name)
    ).unique().all()

    prov_names = {p.code: p.name for p in db.scalars(select(Province)).all()}

    # فاز ۶۷: محاسبهٔ bookable با دو کوئری مجموعه‌ای (نه ۲۱۶ کوئری):
    # مشاوران با مدرک تأییدشدهٔ منقضی‌نشده + مشاوران با مجوز تأییدشدهٔ بدون انقضا
    today = date.today()
    cred_ok: set = set()
    for cid, exp in db.execute(
        select(CounselorCredential.counselor_id, CounselorCredential.expires_at).where(
            CounselorCredential.verification_status == CredentialVerificationStatus.APPROVED,
        )
    ).all():
        if exp is None or exp >= today:
            cred_ok.add(cid)

    def _bookable(c) -> bool:
        if c.id in cred_ok:
            return True
        return bool(c.license_verified) and (
            c.license_expiry_date is None or c.license_expiry_date >= today
        )

    items: list[dict] = []
    total_counselors = 0
    all_counselor_ids: list = []
    per_branch: list[tuple] = []
    for b in branches:
        counselors = db.scalars(
            select(Counselor)
            .where(Counselor.branch_id == b.id, Counselor.status == "active")
        ).all()
        total_counselors += len(counselors)
        all_counselor_ids.extend(c.id for c in counselors)
        per_branch.append((b, counselors))
    # فاز ۶۹: امتیاز هر مشاور برای مرتب‌سازی «بالاترین امتیاز اول»
    from app.models.reviews import CounselorReview

    ratings: dict = {}
    if all_counselor_ids:
        for cid, avg, cnt in db.execute(
            select(
                CounselorReview.counselor_id,
                func.avg(CounselorReview.rating),
                func.count(),
            )
            .where(
                CounselorReview.counselor_id.in_(all_counselor_ids),
                CounselorReview.is_published.is_(True),
            )
            .group_by(CounselorReview.counselor_id)
        ).all():
            ratings[cid] = (float(avg), int(cnt))

    for b, counselors in per_branch:
        def _c_sort(c):
            avg, cnt = ratings.get(c.id, (0.0, 0))
            return (-(avg or 0.0), -cnt, c.last_name, c.first_name)

        counselors = sorted(counselors, key=_c_sort)
        items.append({
            "id": str(b.id),
            "name": b.name,
            "clinic_name": b.clinic.name if b.clinic else None,
            "province_code": b.province_code,
            "province": prov_names.get(b.province_code) if b.province_code else b.province,
            "city": b.city,
            "address": b.address,
            "postal_code": b.postal_code,
            "phone": b.phone,
            "manager_name": b.manager_name,
            "manager_phone": b.manager_phone,
            "exec_name": b.exec_name,
            "exec_phone": b.exec_phone,
            "working_hours": (b.working_hours or {}).get("text") if b.working_hours else None,
            "latitude": float(b.latitude) if b.latitude is not None else None,
            "longitude": float(b.longitude) if b.longitude is not None else None,
            "map_url": b.map_url,
            "counselor_count": len(counselors),
            "counselors": [
                {
                    "id": str(c.id),
                    "name": f"{c.first_name} {c.last_name}".strip(),
                    "degree": c.degree,
                    "license": c.license_number,
                    "bookable": _bookable(c),
                    # فاز ۶۹: امتیاز برای نمایش ستاره‌ها در کارت کلینیک
                    "rating_avg": (
                        round(ratings[c.id][0], 1)
                        if c.id in ratings and ratings[c.id][0]
                        else None
                    ),
                    "review_count": ratings.get(c.id, (0.0, 0))[1],
                }
                for c in counselors
            ],
        })
    return {"items": items, "total": len(items), "total_counselors": total_counselors}
