"""APIهای عمومی سایت (بدون احراز هویت) - فاز ۱۰ + رزرو آنلاین فاز ۲۱ + فاز ۶۹ پرداخت آنلاین و امتیازدهی"""
import re
import secrets
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.booking import (
    bookable_range, free_slots, release_stale_unpaid_requests, validate_slot,
)
from app.core.config import get_settings
from app.core.dates import normalize_digits
from app.db.session import get_db
from app.models.booking import SlotClaim, SlotClaimStatus
from app.models.catalog import Service, ServiceStatus
from app.models.consultation import ConsultPaymentStatus, ConsultationRequest
from app.models.people import Counselor
from app.models.reviews import CounselorReview
from app.services import booking_hold, otp as otp_service
from app.services import payments as pay_svc
from app.services.audit import record_audit
from app.services.qualification import bookable_counselors, is_counselor_bookable

router = APIRouter(prefix="/public", tags=["public"])
settings = get_settings()

# محدودسازی نرخ ثبت درخواست: حداکثر ۵ درخواست در ساعت از هر IP
_req_ip: dict[str, list[float]] = {}
_RATE = 5
_WINDOW = 3600.0

# محدودسازی نرخ ساخت نگهداشت: حداکثر ۱۲ در ساعت از هر IP (فاز ۲۶ - B09)
_hold_ip: dict[str, list[float]] = {}
_HOLD_RATE = 12
_HOLD_WINDOW = 3600.0


def _rate_ok(ip: str) -> bool:
    now = time.monotonic()
    lst = [t for t in _req_ip.get(ip, []) if now - t < _WINDOW]
    if len(lst) >= _RATE:
        _req_ip[ip] = lst
        return False
    lst.append(now)
    _req_ip[ip] = lst
    return True


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _normalize_mobile(raw: str) -> str:
    return otp_service.normalize_mobile(raw)


def _hold_rate_ok(ip: str) -> bool:
    now = time.monotonic()
    lst = [t for t in _hold_ip.get(ip, []) if now - t < _HOLD_WINDOW]
    if len(lst) >= _HOLD_RATE:
        _hold_ip[ip] = lst
        return False
    lst.append(now)
    _hold_ip[ip] = lst
    return True


def _active_holds_for_ip(db: Session, ip: str) -> int:
    return int(db.scalar(
        select(func.count()).select_from(SlotClaim).where(
            SlotClaim.ip == ip,
            SlotClaim.status == SlotClaimStatus.ACTIVE,
            SlotClaim.expires_at > datetime.now(timezone.utc),
        )
    ) or 0)


class ConsultationCreate(BaseModel):
    full_name: str = Field(min_length=3, max_length=200)
    mobile: str = Field(min_length=10, max_length=20)
    topic: str = Field(min_length=2, max_length=100)
    preferred_date: str | None = Field(default=None, max_length=10, pattern=r"^\d{4}-\d{2}-\d{2}$")
    preferred_slot: str | None = Field(default=None, max_length=30)
    message: str | None = Field(default=None, max_length=2000)
    website: str | None = Field(default=None, max_length=100)  # honeypot ضدربات
    city: str | None = Field(default=None, max_length=100)
    referral_source: str | None = Field(default=None, max_length=200)
    # فاز ۲۱ - رزرو آنلاین اسلات
    counselor_id: uuid.UUID | None = None
    start_at: str | None = Field(default=None, max_length=64)
    # فاز ۲۶ - B09/B02: توکن نگهداشت اسلات + توکن اثبات تأیید موبایل
    hold_token: str | None = Field(default=None, max_length=100)
    otp_token: str | None = Field(default=None, max_length=100)
    # فاز ۲۸ - B06: خدمت انتخابی (اختیاری؛ باید فعال باشد)
    service_id: uuid.UUID | None = None
    # فاز ۶۹ - پرداخت آنلاین رزرو در درگاه (زرین‌پال/شبیه‌ساز)
    pay_online: bool = False


@router.get("/counselors")
def public_counselors(db: Session = Depends(get_db)) -> dict:
    """فاز ۲۸ - B05: فقط مشاوران با صلاحیت معتبر در فهرست قابل رزرو می‌آیند.

    فاز ۶۷: استان هر مشاور (از شعبهٔ متصل) هم برمی‌گردد تا صفحهٔ رزرو
    فهرست را بر اساس انتخاب استان فیلتر کند.
    فاز ۶۹: امتیاز میانگین + تعداد نظرات هر مشاور برمی‌گردد و فهرست
    بر اساس امتیاز (بالاترین اول) مرتب می‌شود — در نبود امتیاز، ترتیب الفبایی.
    """
    from app.models.branch import Branch

    items = bookable_counselors(db)
    branch_ids = {c.branch_id for c in items if c.branch_id}
    branches = {}
    if branch_ids:
        for b in db.scalars(select(Branch).where(Branch.id.in_(branch_ids))).all():
            branches[b.id] = b
    ratings = _rating_summary(db, [c.id for c in items])

    def _sort_key(c: Counselor):
        avg, cnt = ratings.get(c.id, (0.0, 0))
        return (-(avg or 0.0), -cnt, c.last_name)

    return {"items": [{
        "id": str(c.id),
        "name": f"{c.first_name} {c.last_name}",
        "professional_title": c.professional_title,
        "specialty": c.specialty,
        "photo_url": f"/api/v1/public/counselors/{c.id}/photo" if c.photo_path else None,
        "province_code": branches[c.branch_id].province_code if c.branch_id in branches else None,
        "province_name": branches[c.branch_id].province if c.branch_id in branches else None,
        "branch_name": branches[c.branch_id].name if c.branch_id in branches else None,
        "rating_avg": round(avg, 1) if (avg := ratings.get(c.id, (0.0, 0))[0]) else None,
        "review_count": ratings.get(c.id, (0.0, 0))[1],
    } for c in sorted(items, key=_sort_key)]}


# ---------------- فاز ۶۹ - امتیازدهی و نظرات مشاوران ----------------

def _rating_summary(db: Session, counselor_ids) -> dict:
    """میانگین امتیاز و تعداد نظرات منتشرشده به تفکیک مشاور."""
    ids = [c for c in set(counselor_ids) if c is not None]
    if not ids:
        return {}
    rows = db.execute(
        select(
            CounselorReview.counselor_id,
            func.avg(CounselorReview.rating),
            func.count(),
        )
        .where(
            CounselorReview.counselor_id.in_(ids),
            CounselorReview.is_published.is_(True),
        )
        .group_by(CounselorReview.counselor_id)
    ).all()
    return {r[0]: (float(r[1]), int(r[2])) for r in rows}


def _mask_name(full: str | None) -> str:
    """نام نویسنده نظر برای نمایش عمومی: «علی رضایی» → «علی ر.»"""
    parts = (full or "").strip().split()
    if not parts:
        return "کاربر رز"
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} {(parts[1] or '')[0]}."


@router.get("/services")
def public_services(db: Session = Depends(get_db)) -> dict:
    """فاز ۲۸ - B06/B07: خدمات فعال + قیمت جاری از تعرفه نسخه‌دار."""
    from app.api.v1.catalog import current_tariff

    items = db.scalars(
        select(Service).where(Service.status == ServiceStatus.ACTIVE).order_by(Service.title)
    ).all()
    out = []
    for s in items:
        t = current_tariff(db, s.id)
        out.append({
            "id": str(s.id),
            "title": s.title,
            "description": s.description,
            "duration_minutes": s.duration_minutes,
            "session_type": s.session_type,
            "price_amount": float(t.amount) if t else None,
            "price_currency": t.currency if t else None,
        })
    return {"items": out}


_PHOTO_MEDIA = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


@router.get("/counselors/{counselor_id}/photo")
def counselor_photo(counselor_id: uuid.UUID, db: Session = Depends(get_db)):
    c = db.get(Counselor, counselor_id)
    if c is None or not c.photo_path:
        raise HTTPException(status_code=404, detail="عکس یافت نشد")
    base = Path("uploads").resolve()
    p = (base / c.photo_path).resolve()
    if not str(p).startswith(str(base)) or not p.is_file():
        raise HTTPException(status_code=404, detail="عکس یافت نشد")
    media = _PHOTO_MEDIA.get(p.suffix.lower(), "application/octet-stream")
    return FileResponse(p, media_type=media)


@router.get("/counselors/{counselor_id}")
def public_counselor_profile(counselor_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    """فاز ۶۹ - پروفایل عمومی مشاور (الگوی اسنپ‌داکتر) برای صفحهٔ متخصص."""
    from app.models.branch import Branch

    c = db.get(Counselor, counselor_id)
    if c is None or not is_counselor_bookable(db, c):
        raise HTTPException(status_code=404, detail="مشاور یافت نشد یا فعال نیست")
    branch = db.get(Branch, c.branch_id) if c.branch_id else None
    avg, cnt = _rating_summary(db, [c.id]).get(c.id, (0.0, 0))
    return {
        "id": str(c.id),
        "name": f"{c.first_name} {c.last_name}",
        "professional_title": c.professional_title,
        "specialty": c.specialty,
        "degree": c.degree,
        "photo_url": f"/api/v1/public/counselors/{c.id}/photo" if c.photo_path else None,
        "province_code": branch.province_code if branch else None,
        "province_name": branch.province if branch else None,
        "branch_name": branch.name if branch else None,
        "rating_avg": round(avg, 1) if avg else None,
        "review_count": cnt,
    }


@router.get("/counselors/{counselor_id}/reviews")
def public_counselor_reviews(counselor_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    """فاز ۶۹ - نظرات منتشرشدهٔ یک مشاور + خلاصهٔ امتیازها."""
    c = db.get(Counselor, counselor_id)
    if c is None:
        raise HTTPException(status_code=404, detail="مشاور یافت نشد")
    rows = db.scalars(
        select(CounselorReview)
        .where(
            CounselorReview.counselor_id == counselor_id,
            CounselorReview.is_published.is_(True),
        )
        .order_by(CounselorReview.created_at.desc())
        .limit(50)
    ).all()
    cr_ids = [r.consultation_request_id for r in rows if r.consultation_request_id]
    cr_names: dict = {}
    if cr_ids:
        for cr in db.scalars(
            select(ConsultationRequest).where(ConsultationRequest.id.in_(cr_ids))
        ).all():
            cr_names[cr.id] = cr.full_name
    breakdown = {str(k): 0 for k in range(1, 6)}
    items = []
    for r in rows:
        breakdown[str(r.rating)] = breakdown.get(str(r.rating), 0) + 1
        author = cr_names.get(r.consultation_request_id) if r.consultation_request_id else None
        items.append({
            "id": str(r.id),
            "rating": r.rating,
            "comment": r.comment,
            "author": _mask_name(author),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    avg, cnt = _rating_summary(db, [counselor_id]).get(counselor_id, (0.0, 0))
    return {
        "items": items,
        "summary": {"rating_avg": round(avg, 1) if avg else None, "review_count": cnt,
                    "breakdown": breakdown},
    }


class ReviewCreate(BaseModel):
    review_token: str = Field(min_length=16, max_length=64)
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


@router.post("/counselors/{counselor_id}/reviews", status_code=201)
def create_counselor_review(
    counselor_id: uuid.UUID, payload: ReviewCreate, db: Session = Depends(get_db),
) -> dict:
    """ثبت نظر برای رزرو پرداخت‌شده - توکن دعوت فقط از مسیر بازگشت موفق
    درگاه (فاز ۶۹) صادر می‌شود؛ برای هر رزرو حداکثر یک نظر."""
    from app.models.payment import Order

    c = db.get(Counselor, counselor_id)
    if c is None:
        raise HTTPException(status_code=404, detail="مشاور یافت نشد")
    cr = db.scalars(
        select(ConsultationRequest).where(ConsultationRequest.review_token == payload.review_token)
    ).first()
    if cr is None:
        raise HTTPException(status_code=403, detail="توکن ثبت نظر نامعتبر است")
    if cr.preferred_counselor_id is None or str(cr.preferred_counselor_id) != str(counselor_id):
        raise HTTPException(status_code=403, detail="این توکن برای نظر دادن به این مشاور نیست")
    if cr.payment_status != ConsultPaymentStatus.PAID:
        raise HTTPException(status_code=403, detail="ثبت نظر فقط برای رزروهای پرداخت‌شده فعال است")
    dup = db.scalars(
        select(CounselorReview.id).where(
            CounselorReview.consultation_request_id == cr.id
        )
    ).first()
    if dup is not None:
        raise HTTPException(status_code=409, detail="برای این نوبت قبلاً نظر ثبت شده است")
    author_user_id = db.scalars(
        select(Order.owner_user_id).where(Order.consultation_request_id == cr.id)
    ).first()
    review = CounselorReview(
        counselor_id=counselor_id,
        author_user_id=author_user_id,
        consultation_request_id=cr.id,
        rating=payload.rating,
        comment=(payload.comment or "").strip() or None,
        is_published=True,
    )
    db.add(review)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="برای این نوبت قبلاً نظر ثبت شده است")
    db.refresh(review)
    record_audit(db, action="public.counselor_review_created",
                 entity_type="counselor_review", entity_id=str(review.id))
    return {
        "status": "ok",
        "id": str(review.id),
        "rating": review.rating,
        "comment": review.comment,
    }


@router.get("/booking/slots")
def booking_slots(
    counselor_id: uuid.UUID,
    from_date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    to_date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    db: Session = Depends(get_db),
) -> dict:
    """اسلات‌های آزاد یک مشاور برای رزرو عمومی (فاز ۲۱) - B05: فقط مشاور با صلاحیت معتبر"""
    c = db.get(Counselor, counselor_id)
    if c is None or not is_counselor_bookable(db, c):
        raise HTTPException(status_code=404, detail="مشاور یافت نشد یا فعال نیست")
    f_default, t_default = bookable_range()
    try:
        f_day = date.fromisoformat(from_date) if from_date else f_default
        t_day = date.fromisoformat(to_date) if to_date else min(f_day + timedelta(days=13), t_default)
    except ValueError:
        raise HTTPException(status_code=422, detail="تاریخ نامعتبر است")
    if t_day < f_day:
        raise HTTPException(status_code=422, detail="بازه تاریخ نامعتبر است")
    return {
        "counselor": {
            "id": str(c.id),
            "name": f"{c.first_name} {c.last_name}",
            "specialty": c.specialty,
        },
        "range": {"from": f_day.isoformat(), "to": t_day.isoformat()},
        "days": free_slots(db, c.id, f_day, t_day),
    }


# ---------------- فاز ۲۶ - B09: نگهداشت موقت اسلات ----------------

class HoldCreate(BaseModel):
    counselor_id: uuid.UUID
    start_at: str = Field(max_length=64)


@router.post("/booking-holds", status_code=201)
def create_booking_hold(payload: HoldCreate, request: Request, db: Session = Depends(get_db)) -> dict:
    """نگهداشت موقت اسلات برای تکمیل فرم (پیش‌فرض ۱۰ دقیقه)."""
    ip = _client_ip(request)
    if not _hold_rate_ok(ip):
        raise HTTPException(status_code=429, detail="تلاش‌های نگهداشت زیاد است؛ کمی بعد دوباره تلاش کنید")
    if _active_holds_for_ip(db, ip) >= settings.booking_hold_max_per_ip:
        raise HTTPException(status_code=429, detail="نگهداشت‌های فعال شما زیاد است؛ یکی را تکمیل یا رها کنید")

    counselor = db.get(Counselor, payload.counselor_id)
    if counselor is None or not is_counselor_bookable(db, counselor):
        raise HTTPException(status_code=422, detail="مشاور انتخاب‌شده فعال نیست یا صلاحیت معتبری ندارد")
    try:
        raw = datetime.fromisoformat(payload.start_at)
    except ValueError:
        raise HTTPException(status_code=422, detail="زمان رزرو نامعتبر است")

    # فاز ۶۹: رزروهای pending پرداخت‌نشدهٔ منقضی → archived (آزادسازی ایندکس اسلات)
    release_stale_unpaid_requests(db)
    booking_hold.expire_stale_holds(db)
    normalized = validate_slot(db, counselor.id, raw)
    if normalized is None:
        raise HTTPException(status_code=409, detail="این زمان در دسترس نیست؛ اسلات دیگری انتخاب کنید")

    res = booking_hold.create_hold(db, counselor.id, normalized, ip=ip)
    if res["conflict"]:
        raise HTTPException(status_code=409, detail="این اسلات هم‌اکنون توسط کاربر دیگری نگه داشته شده است")
    hold = res["hold"]
    record_audit(db, action="public.booking_hold_created",
                 entity_type="slot_claim", entity_id=str(hold.id), ip=ip)
    return {
        "hold_id": str(hold.id),
        "hold_token": res["token"],
        "expires_at": hold.expires_at.isoformat(),
        "remaining_seconds": booking_hold.remaining_seconds(hold),
        "counselor": {"id": str(counselor.id), "name": f"{counselor.first_name} {counselor.last_name}"},
        "start_at": normalized.isoformat(),
        "hold_minutes": settings.booking_hold_minutes,
    }


@router.get("/booking-holds/{hold_token}")
def get_booking_hold(hold_token: str, db: Session = Depends(get_db)) -> dict:
    """وضعیت نگهداشت برای همگام‌سازی شمارش معکوس سمت کاربر."""
    hold = booking_hold.get_hold_by_token(db, hold_token)
    if hold is None:
        raise HTTPException(status_code=404, detail="نگهداشت یافت نشد")
    st = booking_hold.effective_status(hold)
    c = db.get(Counselor, hold.counselor_id)
    return {
        "status": st,
        "start_at": hold.start_at.isoformat(),
        "expires_at": hold.expires_at.isoformat(),
        "remaining_seconds": booking_hold.remaining_seconds(hold),
        "counselor_name": f"{c.first_name} {c.last_name}" if c else None,
    }


@router.delete("/booking-holds/{hold_token}", status_code=204)
def release_booking_hold(hold_token: str, db: Session = Depends(get_db)) -> Response:
    hold = booking_hold.get_hold_by_token(db, hold_token)
    if hold is None:
        raise HTTPException(status_code=404, detail="نگهداشت یافت نشد")
    booking_hold.release_hold(db, hold)
    return Response(status_code=204)


@router.get("/booking-result-info")
def booking_result_info(
    req: str = Query(max_length=64),
    token: str = Query(max_length=64),
    db: Session = Depends(get_db),
) -> dict:
    """فاز ۶۹ - اطلاعات نمایشی نتیجهٔ رزرو (بدون احراز هویت): صرفاً با
    جفت (شناسهٔ درخواست + توکن دعوت) که فقط به کاربر پرداخت‌کننده داده
    می‌شود؛ خروجی حداقلی برای صفحهٔ نتیجهٔ سایت."""
    from app.models.payment import Order

    try:
        rid = uuid.UUID(req)
    except ValueError:
        raise HTTPException(status_code=404, detail="درخواست یافت نشد")
    cr = db.get(ConsultationRequest, rid)
    if cr is None or not cr.review_token or cr.review_token != token:
        raise HTTPException(status_code=404, detail="درخواست یافت نشد")
    if cr.payment_status != ConsultPaymentStatus.PAID:
        raise HTTPException(status_code=404, detail="درخواست یافت نشد")
    counselor_id = str(cr.preferred_counselor_id) if cr.preferred_counselor_id else None
    counselor_name = None
    if cr.preferred_counselor_id is not None:
        c = db.get(Counselor, cr.preferred_counselor_id)
        counselor_name = f"{c.first_name} {c.last_name}" if c else None
    service_title = None
    if cr.service_id is not None:
        svc = db.get(Service, cr.service_id)
        service_title = svc.title if svc else None
    amount = None
    order = db.scalars(select(Order).where(Order.consultation_request_id == cr.id)).first()
    if order is not None:
        amount = int(order.payable_amount)
    return {
        "counselor_id": counselor_id,
        "counselor_name": counselor_name,
        "service_title": service_title,
        "start_at": cr.preferred_start_at.isoformat() if cr.preferred_start_at else None,
        "slot": cr.preferred_slot,
        "amount": amount,
        "full_name": cr.full_name,
    }


@router.post("/consultation-requests", status_code=201)
def submit_consultation(payload: ConsultationCreate, request: Request, db: Session = Depends(get_db)) -> dict:
    ip = _client_ip(request)
    # هانی‌پات: ربات‌ها فیلد مخفی را پر می‌کنند — پاسخ موفق جعلی بدون ذخیره
    if payload.website and payload.website.strip():
        return {"status": "ok"}
    if not _rate_ok(ip):
        raise HTTPException(status_code=429, detail="تعداد درخواست‌ها زیاد است؛ کمی بعد دوباره تلاش کنید")
    # فاز ۶۹: آزادسازی رزروهای pending منقضی پیش از اعتبارسنجی اسلات
    release_stale_unpaid_requests(db)

    mobile = _normalize_mobile(payload.mobile)
    if not re.fullmatch(r"09\d{9}", mobile):
        raise HTTPException(status_code=422, detail="شماره موبایل معتبر نیست (نمونه: 09121234567)")

    # فاز ۲۶ - B02: تأیید موبایل با کد یک‌بارمصرف (الزامی وقتی BOOKING_REQUIRE_OTP=true)
    otp_ok = False
    if payload.otp_token:
        if not otp_service.consume_verify_token(db, payload.otp_token, mobile):
            raise HTTPException(status_code=403, detail="تأیید موبایل نامعتبر یا منقضی است؛ کد جدید بگیرید")
        otp_ok = True
    elif settings.booking_require_otp:
        raise HTTPException(status_code=403, detail="تأیید موبایل با کد یک‌بارمصرف الزامی است")

    preferred = None
    if payload.preferred_date:
        try:
            preferred = datetime.strptime(payload.preferred_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=422, detail="تاریخ نامعتبر است")

    # فاز ۲۸ - B06: خدمت انتخابی باید فعال باشد (خدمت غیرفعال رزرو جدید نمی‌گیرد)
    selected_service = None
    if payload.service_id is not None:
        selected_service = db.get(Service, payload.service_id)
        if selected_service is None:
            raise HTTPException(status_code=404, detail="خدمت یافت نشد")
        if selected_service.status != ServiceStatus.ACTIVE:
            raise HTTPException(status_code=409, detail="این خدمت غیرفعال است و رزرو جدید نمی‌پذیرد")

    # فاز ۶۹ - پیش‌شرط‌های پرداخت آنلاین: رزرو اسلات + خدمت با تعرفه معتبر
    booking_tariff = None
    if payload.pay_online:
        if payload.counselor_id is None and payload.hold_token is None:
            raise HTTPException(status_code=422, detail="پرداخت آنلاین فقط برای رزرو نوبت فعال است")
        if selected_service is None:
            raise HTTPException(status_code=422, detail="برای پرداخت آنلاین، انتخاب خدمت الزامی است")
        from app.api.v1.catalog import current_tariff

        on_date = preferred.date() if preferred else date.today()
        booking_tariff = current_tariff(db, selected_service.id, on_date)
        if booking_tariff is None:
            raise HTTPException(
                status_code=422,
                detail="برای این خدمت تعرفهٔ فعالی ثبت نشده است؛ لطفاً با پشتیبانی تماس بگیرید",
            )

    # فاز ۲۱/۲۶ - اعتبارسنجی رزرو اسلات (با یا بدون نگهداشت)
    preferred_counselor_id = None
    preferred_start = None
    slot_label = payload.preferred_slot
    hold = None
    if payload.counselor_id is not None or payload.start_at or payload.hold_token:
        if payload.hold_token:
            # مسیر hold: اعتبارسنجی نگهداشت به‌جای اسلات (hold خودش اسلات را رزرو کرده است)
            if payload.counselor_id is None:
                raise HTTPException(status_code=422, detail="برای رزرو، انتخاب مشاور و زمان هر دو الزامی است")
            booking_hold.expire_stale_holds(db)
            hold = booking_hold.get_hold_by_token(db, payload.hold_token)
            if hold is None or booking_hold.effective_status(hold) != "active":
                raise HTTPException(status_code=409, detail="زمان نگهداشت منقضی شده است؛ لطفاً اسلات را دوباره انتخاب کنید")
            if str(hold.counselor_id) != str(payload.counselor_id):
                raise HTTPException(status_code=409, detail="نگهداشت با مشاور انتخاب‌شده مطابقت ندارد")
            counselor = db.get(Counselor, hold.counselor_id)
            if counselor is None or not is_counselor_bookable(db, counselor):
                raise HTTPException(status_code=422, detail="مشاور انتخاب‌شده فعال نیست یا صلاحیت معتبری ندارد")
            preferred_counselor_id = counselor.id
            preferred_start = hold.start_at
            slot_label = preferred_start.strftime("%H:%M")
        else:
            if payload.counselor_id is None or not payload.start_at:
                raise HTTPException(status_code=422, detail="برای رزرو، انتخاب مشاور و زمان هر دو الزامی است")
            counselor = db.get(Counselor, payload.counselor_id)
            if counselor is None or not is_counselor_bookable(db, counselor):
                raise HTTPException(status_code=422, detail="مشاور انتخاب‌شده فعال نیست یا صلاحیت معتبری ندارد")
            try:
                raw = datetime.fromisoformat(payload.start_at)
            except ValueError:
                raise HTTPException(status_code=422, detail="زمان رزرو نامعتبر است")
            normalized = validate_slot(db, counselor.id, raw)
            if normalized is None:
                raise HTTPException(status_code=409, detail="این زمان دیگر در دسترس نیست؛ لطفاً اسلات دیگری انتخاب کنید")
            preferred_counselor_id = counselor.id
            preferred_start = normalized
            slot_label = normalized.strftime("%H:%M")

    r = ConsultationRequest(
        full_name=payload.full_name.strip(),
        mobile=mobile,
        topic=payload.topic.strip(),
        preferred_date=preferred,
        preferred_slot=slot_label,
        message=payload.message,
        city=payload.city,
        referral_source=payload.referral_source,
        ip=ip,
        preferred_counselor_id=preferred_counselor_id,
        preferred_start_at=preferred_start,
        service_id=selected_service.id if selected_service is not None else None,
        payment_status=(
            ConsultPaymentStatus.PENDING if payload.pay_online
            else ConsultPaymentStatus.NOT_REQUIRED
        ),
    )
    db.add(r)
    try:
        db.commit()
    except IntegrityError:
        # ایندکس یکتای جزئی: دو رزرو هم‌زمان روی یک اسلات
        db.rollback()
        raise HTTPException(status_code=409, detail="این زمان هم‌اکنون رزرو شد؛ اسلات دیگری انتخاب کنید")
    # فاز ۲۶ - B09: تبدیل نگهداشت به رزرو تأییدشده
    if hold is not None:
        booking_hold.confirm_hold(db, hold, r.id, mobile)
    record_audit(db, action="public.consultation_requested",
                 entity_type="consultation_request", entity_id=str(r.id), ip=ip,
                 detail={"booking": preferred_start is not None,
                         "hold": hold is not None, "otp_verified": otp_ok,
                         "pay_online": payload.pay_online})

    resp: dict = {"status": "ok", "request_id": str(r.id)}

    # ---------------- فاز ۶۹ - پرداخت آنلاین رزرو (زرین‌پال/شبیه‌ساز) ----------------
    if payload.pay_online:
        user = _get_or_create_booking_user(db, mobile, payload.full_name)
        from app.models.payment import Order, OrderStatus

        counselor_name = None
        if preferred_counselor_id is not None:
            cc = db.get(Counselor, preferred_counselor_id)
            counselor_name = f"{cc.first_name} {cc.last_name}" if cc else None
        order = Order(
            order_number=pay_svc.generate_order_number(db),
            owner_user_id=user.id,
            service_id=selected_service.id,
            tariff_version_id=booking_tariff.id,
            title=(
                f"{selected_service.title}" + (f" - {counselor_name}" if counselor_name else "")
            )[:300],
            amount=booking_tariff.amount,
            currency=booking_tariff.currency,
            payable_amount=booking_tariff.amount,
            status=OrderStatus.PENDING,
            kind="service",
            consultation_request_id=r.id,
            note=f"رزرو آنلاین نوبت {slot_label or ''}"[:500],
        )
        db.add(order)
        db.commit()
        db.refresh(order)
        try:
            init = pay_svc.initiate_payment(db, order, gateway=pay_svc.public_default_gateway())
        except pay_svc.GatewayError as exc:
            # رزرو ثبت شده است ولی اتصال به درگاه ناموفق - پذیرش کنسری (B12):
            # نتیجهٔ رزرو برنمی‌گردد؛ پیام خطا برای ادامهٔ کار نمایش داده می‌شود.
            record_audit(db, action="public.booking_payment_init_failed",
                         entity_type="order", entity_id=str(order.id), ip=ip,
                         detail={"reason": str(exc)[:200]})
            resp["payment_error"] = str(exc)
        else:
            resp["payment"] = {
                "redirect_url": init.redirect_url,
                "authority": init.payment.authority,
                "gateway": init.payment.gateway,
                "order_number": order.order_number,
                "amount": int(order.payable_amount),
                "currency": order.currency,
            }
    return resp


def _get_or_create_booking_user(db: Session, mobile: str, full_name: str | None):
    """فاز ۶۹ - حساب کاربری خودکار برای مالکیت سفارش پرداخت (ورود با OTP
    انجام شده است؛ بدون رمز عبور - username همان موبایل نرمال‌شده)."""
    from app.models.user import User, UserStatus

    u = db.scalars(select(User).where(User.username == mobile)).first()
    if u is not None:
        return u
    u = User(
        username=mobile,
        display_name=(full_name or mobile).strip()[:200] or mobile,
        mobile=mobile,
        password_hash=None,
        status=UserStatus.ACTIVE,
    )
    db.add(u)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        u = db.scalars(select(User).where(User.username == mobile)).first()
    return u