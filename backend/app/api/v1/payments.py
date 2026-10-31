"""فاز ۲۹ - B10/B11 سند جامع: سفارش، پرداخت و فاکتور.

B10 قواعد سند:
- سفارش از snapshot قیمت نوبت/تعرفه ساخته می‌شود (B07: قیمت گذشته تغییر نکند)؛
- پرداخت فقط پس از «تأیید قطعی سمت سرور» موفق است؛ callback تکراری بی‌اثر؛
- شکست اعلان، پرداخت موفق را برنمی‌گرداند (B12).

B11 قواعد سند:
- پس از پرداخت موفق دقیقاً یک فاکتور با شماره یکتا؛ مبلغ فاکتور با
  snapshot سفارش منطبق است.
"""
import secrets
import uuid
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.core.booking import validate_slot
from app.core.config import get_settings
from app.models.appointment import Appointment
from app.models.case import Case
from app.models.catalog import Service
from app.models.consultation import ConsultPaymentStatus, ConsultationRequest
from app.models.org_contract import Contract, ContractService
from app.models.people import Applicant
from app.models.payment import Invoice, InvoiceItem, Order, OrderStatus
from app.models.user import User
from app.services import payments as pay
from app.services.notifications import notify_user

router = APIRouter(tags=["payments"])

VIEW_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER", "TECHNICAL_SUPERVISOR", "RECEPTION", "COUNSELOR")
CREATE_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION")


def _active_contract_for(db: Session, organization_id, service_id):
    """B21: قرارداد فعال سازمان برای خدمت — draft/منقضی/ملغی اعمال نمی‌شود؛
    بدون ردیف دامنه = همه خدمات؛ با ردیف = فقط همان خدمات."""
    from datetime import date

    today = date.today()
    contracts = db.scalars(
        select(Contract).where(
            Contract.organization_id == organization_id,
            Contract.status == "active",
            Contract.valid_from <= today,
        )
    ).all()
    candidates = [c for c in contracts if c.valid_to is None or c.valid_to >= today]
    for c in candidates:
        scoped = db.scalars(
            select(ContractService.service_id).where(ContractService.contract_id == c.id)
        ).all()
        if not scoped or service_id in scoped:
            return c
    return None


def _order_number(db: Session) -> str:
    """فاز ۳۴: تولید شماره سفارش به سرویس مشترک منتقل شد (سفارش دوره/آزمون هم همان را می‌گیرد)."""
    return pay.generate_order_number(db)


def _order_out(db: Session, o: Order, with_invoice: bool = True) -> dict:
    data = {
        "id": str(o.id),
        "order_number": o.order_number,
        "owner_user_id": str(o.owner_user_id),
        "case_id": str(o.case_id) if o.case_id else None,
        "appointment_id": str(o.appointment_id) if o.appointment_id else None,
        "service_id": str(o.service_id) if o.service_id else None,
        "title": o.title,
        "amount": float(o.amount),
        "currency": o.currency,
        "discount_amount": float(o.discount_amount) if o.discount_amount is not None else None,
        "payable_amount": float(o.payable_amount),
        "status": o.status,
        "kind": getattr(o, "kind", "service"),
        "discount_code": None,
        "refunded_amount": float(getattr(o, "refunded_amount", 0) or 0),
        # فاز ۳۳ - B21: تقسیم سهم پرداخت (snapshot)
        "organization_id": str(o.organization_id) if o.organization_id else None,
        "contract_id": str(o.contract_id) if o.contract_id else None,
        "coverage_percent": float(o.coverage_percent) if o.coverage_percent is not None else None,
        "org_share_amount": float(o.org_share_amount) if o.org_share_amount is not None else None,
        "applicant_share_amount": (
            float(o.applicant_share_amount) if o.applicant_share_amount is not None else None
        ),
        "note": o.note,
        "created_at": o.created_at.isoformat() if o.created_at else None,
    }
    if getattr(o, "discount_id", None):
        from app.models.discount import Discount

        disc = db.get(Discount, o.discount_id)
        data["discount_code"] = disc.code if disc else None
    if with_invoice:
        inv = db.scalars(select(Invoice).where(Invoice.order_id == o.id)).first()
        data["invoice_id"] = str(inv.id) if inv else None
        data["invoice_number"] = inv.invoice_number if inv else None
    return data


def _can_view_order(actor: User, order: Order) -> bool:
    if any(r.code in VIEW_ROLES for r in actor.roles):
        return True
    return order.owner_user_id == actor.id


# ---------------------------------------------------------------- orders
# فاز ۴۲ - ADR-05 گام ۳: مستندسازی هدر Idempotency-Key در OpenAPI برای کلاینت‌ها
# (هدر در میان‌افزار خوانده می‌شود؛ اینجا فقط قراردادِ سند API)
# فاز ۴۳ - تکمیل گام ۴ طرح ADR-05: مستندسازی پاسخ ۴۲۹ سقف نرخ سراسری
# (گام‌های ۱–۲) با هدر Retry-After برای کلاینت‌ها/مشتریان اداری SLA-دار
_IDEMPOTENCY_OPENAPI_EXTRA = {
    "parameters": [
        {
            "name": "Idempotency-Key",
            "in": "header",
            "required": False,
            "description": (
                "کلید یکتای کلاینت (UUID) برای جلوگیری از ثبت دوباره عملیات مالی "
                "(ADR-05 گام ۳) — مثلاً دوبار-زدن دکمه پرداخت روی شبکه ناپایدار. "
                "تکرار همان کلید با همان بدنه → همان پاسخ قبلی؛ همان کلید با "
                "بدنه/مسیر متفاوت → ۴۰۹. تا ۱۲۸ نویسه."
            ),
            "schema": {"type": "string", "minLength": 1, "maxLength": 128},
        }
    ],
    "responses": {
        "429": {
            "description": (
                "سقف نرخ سراسری پر شده است (ADR-05 گام ۲) — کلاینت باید به اندازهٔ "
                "هدر Retry-After (ثانیه) صبر کند؛ هدرهای X-RateLimit-Limit و "
                "X-RateLimit-Remaining برای پایش SLA همراه پاسخ می‌آیند."
            ),
            "headers": {
                "Retry-After": {
                    "description": "ثانیه تا زمان تلاش مجدد مجاز",
                    "schema": {"type": "integer", "minimum": 1},
                },
                "X-RateLimit-Limit": {
                    "description": "سقف مجاز در پنجره جاری",
                    "schema": {"type": "integer"},
                },
                "X-RateLimit-Remaining": {
                    "description": "باقی‌ماندهٔ مجاز در پنجره جاری",
                    "schema": {"type": "integer"},
                },
            },
        }
    },
}


class OrderCreate(BaseModel):
    appointment_id: uuid.UUID | None = None
    service_id: uuid.UUID | None = None
    case_id: uuid.UUID | None = None
    title: str | None = Field(default=None, max_length=300)
    discount_amount: int | None = Field(default=None, ge=0)
    discount_code: str | None = Field(default=None, max_length=50)
    note: str | None = Field(default=None, max_length=500)
    owner_user_id: uuid.UUID | None = None


@router.get("/orders")
def list_orders(
    status: str | None = None,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    q = select(Order).order_by(Order.created_at.desc()).limit(200)
    if status:
        if status not in OrderStatus.ALL:
            raise HTTPException(status_code=422, detail="وضعیت نامعتبر است")
        q = q.where(Order.status == status)
    if not any(r.code in VIEW_ROLES for r in actor.roles):
        q = q.where(Order.owner_user_id == actor.id)
    orders = db.scalars(q).all()
    return {"items": [_order_out(db, o) for o in orders]}


@router.get("/orders/{order_id}")
def get_order(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="سفارش یافت نشد")
    if not _can_view_order(actor, order):
        raise HTTPException(status_code=403, detail="دسترسی به این سفارش مجاز نیست")
    out = _order_out(db, order)
    pays = db.scalars(
        select(pay.Payment).where(pay.Payment.order_id == order.id).order_by(pay.Payment.created_at)
    ).all()
    out["payments"] = [
        {
            "id": str(p.id),
            "gateway": p.gateway,
            "amount": float(p.amount),
            "status": p.status,
            "authority": p.authority,
            "gateway_ref": p.gateway_ref,
            "fail_reason": p.fail_reason,
            "paid_at": p.paid_at.isoformat() if p.paid_at else None,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in pays
    ]
    return out


@router.post("/orders", status_code=201, openapi_extra=_IDEMPOTENCY_OPENAPI_EXTRA)
def create_order(
    payload: OrderCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*CREATE_ROLES)),
) -> dict:
    """ساخت سفارش با snapshot مبلغ از نوبت (اولویت) یا تعرفه جاری خدمت."""
    amount = None
    currency = "IRR"
    tariff_version_id = None
    service_id = payload.service_id
    title = (payload.title or "").strip()

    if payload.appointment_id is not None:
        appt = db.get(Appointment, payload.appointment_id)
        if appt is None:
            raise HTTPException(status_code=404, detail="نوبت یافت نشد")
        dup = db.scalars(select(Order.id).where(Order.appointment_id == appt.id)).first()
        if dup is not None:
            raise HTTPException(status_code=409, detail="برای این نوبت قبلاً سفارش ساخته شده است")
        if appt.price_amount is None:
            raise HTTPException(status_code=422, detail="نوبت فاقد قیمت snapshot است؛ ابتدا تعرفه را ثبت کنید")
        amount = int(appt.price_amount)
        currency = appt.price_currency or "IRR"
        tariff_version_id = appt.tariff_version_id
        service_id = appt.service_id or payload.service_id
        if not title:
            title = "خدمات مشاوره - نوبت"
    elif payload.service_id is not None:
        svc = db.get(Service, payload.service_id)
        if svc is None:
            raise HTTPException(status_code=404, detail="خدمت یافت نشد")
        from app.api.v1.catalog import current_tariff

        tariff = current_tariff(db, svc.id)
        if tariff is None:
            raise HTTPException(status_code=422, detail="برای این خدمت تعرفه معتبری وجود ندارد")
        amount = int(tariff.amount)
        currency = tariff.currency
        tariff_version_id = tariff.id
        if not title:
            title = svc.title
    else:
        raise HTTPException(status_code=422, detail="appointment_id یا service_id لازم است")

    discount = payload.discount_amount or 0
    if payload.discount_code and discount:
        raise HTTPException(status_code=422, detail="کد تخفیف و تخفیف دستی هم‌زمان قابل استفاده نیستند")
    if discount > amount:
        raise HTTPException(status_code=422, detail="تخفیف نمی‌تواند از مبلغ سفارش بیشتر باشد")

    # فاز ۳۳ - B21: تقسیم سهم پرداخت سازمان (قرارداد فعال) — snapshot در لحظه سفارش
    org_id = None
    contract_id = None
    coverage_percent = None
    org_share = 0
    if payload.discount_code or discount:
        # قرارداد و تخفیف هم‌زمان قابل استفاده نیستند (منع دو‌جبری شدن هزینه)
        case_for_org = None
        if payload.case_id is not None:
            case_for_org = db.get(Case, payload.case_id)
        elif payload.appointment_id is not None:
            appt0 = db.get(Appointment, payload.appointment_id)
            case_for_org = db.get(Case, appt0.case_id) if appt0 and appt0.case_id else None
        applicant0 = db.get(Applicant, case_for_org.applicant_id) if case_for_org else None
        if applicant0 is not None and applicant0.organization_id is not None:
            raise HTTPException(
                status_code=422,
                detail="متقاضی دارای سازمان با قرارداد است؛ تخفیف و قرارداد هم‌زمان قابل استفاده نیستند",
            )
    else:
        case_for_org = None
        if payload.case_id is not None:
            case_for_org = db.get(Case, payload.case_id)
        elif payload.appointment_id is not None:
            appt0 = db.get(Appointment, payload.appointment_id)
            case_for_org = db.get(Case, appt0.case_id) if appt0 and appt0.case_id else None
        applicant0 = db.get(Applicant, case_for_org.applicant_id) if case_for_org else None
        if (
            applicant0 is not None
            and applicant0.organization_id is not None
            and service_id is not None
        ):
            contract = _active_contract_for(db, applicant0.organization_id, service_id)
            if contract is not None:
                org_id = contract.organization_id
                contract_id = contract.id
                coverage_percent = float(contract.coverage_percent)
                raw_share = int(round(amount * coverage_percent / 100.0))
                if contract.coverage_cap_amount is not None:
                    raw_share = min(raw_share, int(contract.coverage_cap_amount))
                org_share = max(0, min(raw_share, amount))

    owner = payload.owner_user_id or actor.id
    if db.get(User, owner) is None:
        raise HTTPException(status_code=404, detail="کاربر مالک سفارش یافت نشد")

    order = Order(
        order_number=_order_number(db),
        owner_user_id=owner,
        case_id=payload.case_id,
        appointment_id=payload.appointment_id,
        service_id=service_id,
        tariff_version_id=tariff_version_id,
        title=title[:300],
        amount=amount,
        currency=currency,
        discount_amount=discount if discount else None,
        payable_amount=amount - discount - org_share,
        status=OrderStatus.PENDING,
        organization_id=org_id,
        contract_id=contract_id,
        coverage_percent=coverage_percent,
        org_share_amount=org_share if org_share else None,
        applicant_share_amount=(amount - discount - org_share) if org_share else None,
        note=payload.note,
        created_by=actor.id,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    # فاز ۳۰ - B19: اعمال کد تخفیف پس از ساخت سفارش (کنترل سقف با قفل ردیف)
    if payload.discount_code:
        from app.services.discounts import DiscountError, apply_to_order

        try:
            apply_to_order(db, order, payload.discount_code, owner)
        except DiscountError as exc:
            # rollback، درج سفارش را هم خنثی می‌کند (سفارش بدون کد معتبر نمی‌ماند)
            db.rollback()
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        db.refresh(order)
    return _order_out(db, order)


@router.post("/orders/{order_id}/cancel")
def cancel_order(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*CREATE_ROLES)),
) -> dict:
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="سفارش یافت نشد")
    if order.status == OrderStatus.PAID:
        raise HTTPException(status_code=409, detail="سفارش پرداخت‌شده قابل لغو نیست؛ از استرداد استفاده کنید (B20)")
    if order.status in (OrderStatus.CANCELLED, OrderStatus.FAILED):
        raise HTTPException(status_code=409, detail="سفارش قبلاً بسته شده است")
    order.status = OrderStatus.CANCELLED
    db.commit()
    return _order_out(db, order)


# ---------------------------------------------------------------- payments
class PaymentInit(BaseModel):
    gateway: str | None = Field(default=None, max_length=30)

@router.get("/payments/gateways")
def gateways(_actor: User = Depends(get_current_user)) -> dict:
    return {"items": pay.configured_gateways()}


@router.post("/orders/{order_id}/payments", status_code=201, openapi_extra=_IDEMPOTENCY_OPENAPI_EXTRA)
def start_payment(
    order_id: uuid.UUID,
    payload: PaymentInit,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*CREATE_ROLES)),
) -> dict:
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="سفارش یافت نشد")
    try:
        result = pay.initiate_payment(db, order, payload.gateway)
    except pay.GatewayError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "payment_id": str(result.payment.id),
        "authority": result.payment.authority,
        "gateway": result.payment.gateway,
        "amount": float(result.payment.amount),
        "redirect_url": result.redirect_url,
    }


@router.post("/payments/{authority}/verify")
def verify_payment(
    authority: str,
    approve: bool = True,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    """تأیید قطعی سمت سرور؛ callback تکراری بی‌اثر (idempotent).
    دسترسی: کارکنان مجاز یا مالک سفارش (بازگشت کاربر از درگاه)."""
    try:
        payment, result = pay.verify_payment(db, authority, approve=approve)
    except pay.GatewayError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    order = db.get(Order, payment.order_id)
    if order is not None:
        allowed = any(r.code in CREATE_ROLES for r in actor.roles) or order.owner_user_id == actor.id
        if not allowed:
            raise HTTPException(status_code=403, detail="دسترسی به این تراکنش مجاز نیست")
    if result.ok and order is not None:
        _notify_payment(db, payment, order)
    return {
        "payment_id": str(payment.id),
        "authority": payment.authority,
        "status": payment.status,
        "ok": result.ok,
        "reason": result.reason,
        "gateway_ref": payment.gateway_ref,
        "order_status": order.status if order else None,
        "idempotent": bool((result.payload or {}).get("idempotent")),
    }


@router.post("/payments/callback/{gateway}")
def gateway_callback(
    gateway: str,
    authority: str,
    approve: bool = True,
    db: Session = Depends(get_db),
) -> dict:
    """callback درگاه - همان مسیر verify؛ تکرار آن بی‌اثر است."""
    try:
        payment, result = pay.verify_payment(db, authority, approve=approve)
    except pay.GatewayError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    order = db.get(Order, payment.order_id)
    if result.ok and order is not None and not (result.payload or {}).get("idempotent"):
        _notify_payment(db, payment, order)
    return {
        "authority": payment.authority,
        "status": payment.status,
        "order_status": order.status if order else None,
    }


# ---------------------------------------------------------------- فاز ۶۹ - بازگشت مرورگر از درگاه + رزرو آنلاین

@router.get("/payments/callback/{gateway}")
def gateway_callback_redirect(
    gateway: str,
    authority: str = Query(max_length=120),
    status: str | None = Query(default=None, max_length=10),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """بازگشت مرورگر کاربر از درگاه (زرین‌پال با GET و پارامتر status=OK/NOK
    برمی‌گردد). تأیید قطعی همان مسیر verify سمت سرور است؛ سپس رزرو عمومی
    متصل به سفارش «پرداخت‌شده» می‌شود و توکن ثبت نظر صادر می‌گردد.
    پاسخ: ریدایرکت ۳۰۳ به صفحهٔ نتیجهٔ سایت (/booking/result)."""
    approve = (status or "OK").upper() != "NOK"
    state = "failed"
    req_id = None
    token = None
    try:
        payment, result = pay.verify_payment(db, authority, approve=approve)
        order = db.get(Order, payment.order_id)
        if result.ok and order is not None and not (result.payload or {}).get("idempotent"):
            _notify_payment(db, payment, order)
        if result.ok and order is not None:
            state = "success"
            if order.consultation_request_id is not None:
                cr = db.get(ConsultationRequest, order.consultation_request_id)
                if cr is not None:
                    req_id = str(cr.id)
                    if cr.payment_status != ConsultPaymentStatus.PAID:
                        cr.payment_status = ConsultPaymentStatus.PAID
                        from datetime import datetime, timezone

                        cr.paid_at = datetime.now(timezone.utc)
                    # فاز ۶۹: اگر رزرو پیش از پرداخت منقضی و archived شده باشد،
                    # ابتدا آزاد بودن اسلات کنترل می‌شود؛ آزاد بود → دوباره فعال؛
                    # اشغال شده → archived می‌ماند (پرداخت ثبت است؛ استرداد دستی).
                    if cr.status == "archived" and cr.preferred_counselor_id and cr.preferred_start_at:
                        if validate_slot(db, cr.preferred_counselor_id, cr.preferred_start_at) is not None:
                            cr.status = "new"
                        else:
                            cr.reception_note = ((cr.reception_note or "") +
                                                 " | پرداخت موفق پس از آزادشدن اسلات رسید - بررسی/استرداد دستی")[:2000]
                    if not cr.review_token:
                        cr.review_token = secrets.token_urlsafe(32)
                    token = cr.review_token
                    db.commit()
        elif result.ok is False and order is not None and order.consultation_request_id is not None:
            cr = db.get(ConsultationRequest, order.consultation_request_id)
            if cr is not None and cr.payment_status == ConsultPaymentStatus.PENDING:
                # پرداخت تأیید نشد → رزرو عملاً منتفی است؛ اسلات باید آزاد شود
                cr.payment_status = ConsultPaymentStatus.FAILED
                if cr.status in ("new", "in_review"):
                    cr.status = "archived"
                db.commit()
            if cr is not None:
                req_id = str(cr.id)
    except pay.GatewayError:
        state = "failed"
    params = {"state": state, "gateway": gateway}
    if req_id:
        params["req"] = req_id
    if token:
        params["token"] = token
    base = get_settings().public_base_url.rstrip("/")
    return RedirectResponse(url=f"{base}/booking/result?{urlencode(params)}", status_code=303)


_SANDBOX_PAGE = """<!doctype html>
<html lang="fa" dir="rtl">
<head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>درگاه شبیه‌ساز پرداخت - رزپسی</title>
<style>
 body{font-family:Vazirmatn,Tahoma,sans-serif;background:#f6eef1;margin:0;display:flex;align-items:center;justify-content:center;min-height:100vh}
 .card{background:#fff;border-radius:16px;box-shadow:0 10px 40px rgba(168,58,84,.15);padding:32px;max-width:420px;width:92%;text-align:center}
 h1{color:#7c2740;font-size:18px;margin:0 0 8px} p{color:#6b5560;font-size:14px;margin:6px 0 20px}
 .btn{display:inline-block;width:100%;padding:12px;border-radius:99px;margin:6px 0;text-decoration:none;font-size:15px;font-weight:700}
 .ok{background:linear-gradient(135deg,#a83a54,#c05a72);color:#fff}.nok{background:#fff;color:#a83a54;border:1.5px solid #a83a54}
 code{background:#f6eef1;padding:2px 6px;border-radius:6px;font-size:12px;direction:ltr;display:inline-block}
</style></head>
<body><div class="card">
 <h1>درگاه شبیه‌ساز پرداخت (توسعه)</h1>
 <p>این صفحه جایگزین درگاه واقعی زرین‌پال در محیط توسعه/آزمون است.</p>
 <p>شناسه تراکنش: <code>__AUTH__</code></p>
 <a class="btn ok" href="__CB_OK__">پرداخت موفق (تأیید)</a>
 <a class="btn nok" href="__CB_NOK__">لغو پرداخت</a>
</div></body></html>"""


@router.get("/sandbox-gateway", response_class=HTMLResponse)
def sandbox_gateway_page(authority: str = Query(max_length=120)) -> HTMLResponse:
    """فاز ۶۹ - صفحهٔ شبیه‌ساز درگاه برای محیط توسعه/آزمون؛ دکمه‌های
    تأیید/لغو به همان مسیر callback GET وصل می‌شوند (جریان واقعی درگاه)."""
    import html as _html

    safe = _html.escape(authority, quote=True)
    cb = f"/api/v1/payments/callback/sandbox?authority={safe}"
    page = (
        _SANDBOX_PAGE
        .replace("__AUTH__", safe)
        .replace("__CB_OK__", cb + "&status=OK")
        .replace("__CB_NOK__", cb + "&status=NOK")
    )
    return HTMLResponse(page)


def _notify_payment(db: Session, payment: pay.Payment, order: Order) -> None:
    """اعلان B12 - شکست اعلان هرگز جریان پرداخت را برنمی‌گرداند."""
    try:
        info = pay.payment_notification(payment, order)
        notify_user(
            db,
            recipient_user_id=order.owner_user_id,
            event_code=info["event_code"],
            title=info["title"],
            body=info["body"],
            category=info["category"],
            severity=info["severity"],
            entity_type="order",
            entity_id=str(order.id),
        )
    except Exception:
        db.rollback()


# ---------------------------------------------------------------- invoices
def _invoice_out(db: Session, inv: Invoice) -> dict:
    order = db.get(Order, inv.order_id)
    items = db.scalars(
        select(InvoiceItem).where(InvoiceItem.invoice_id == inv.id).order_by(InvoiceItem.created_at)
    ).all()
    return {
        "id": str(inv.id),
        "invoice_number": inv.invoice_number,
        "order_id": str(inv.order_id),
        "order_number": order.order_number if order else None,
        "total_amount": float(inv.total_amount),
        "currency": inv.currency,
        "buyer_name": inv.buyer_name,
        "buyer_national_id": inv.buyer_national_id,
        "buyer_email": inv.buyer_email,
        "status": inv.status,
        "issued_at": inv.issued_at.isoformat() if inv.issued_at else None,
        "items": [
            {
                "id": str(i.id),
                "description": i.description,
                "quantity": i.quantity,
                "unit_amount": float(i.unit_amount),
                "line_total": float(i.line_total),
            }
            for i in items
        ],
    }


@router.get("/invoices")
def list_invoices(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    q = select(Invoice).order_by(Invoice.issued_at.desc()).limit(200)
    if not any(r.code in VIEW_ROLES for r in actor.roles):
        q = q.join(Order, Order.id == Invoice.order_id).where(Order.owner_user_id == actor.id)
    invoices = db.scalars(q).all()
    return {"items": [_invoice_out(db, i) for i in invoices]}


@router.get("/invoices/{invoice_id}")
def get_invoice(
    invoice_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    inv = db.get(Invoice, invoice_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="فاکتور یافت نشد")
    order = db.get(Order, inv.order_id)
    if not _can_view_order(actor, order):
        raise HTTPException(status_code=403, detail="دسترسی به این فاکتور مجاز نیست")
    return _invoice_out(db, inv)
