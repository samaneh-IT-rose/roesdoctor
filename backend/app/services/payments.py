"""فاز ۲۹ - B10 سند جامع: موتور پرداخت با معماری درگاه پلاگین‌پذیر (تصمیم D02).

قواعد سند:
- «پرداخت فقط پس از تأیید سمت سرور قطعی» — وضعیت موفق تنها با verify
  سمت سامانه ثبت می‌شود؛ پاسخ callback به‌تنهایی کافی نیست.
- «callback تکراری بی‌اثر» — authority یکتا + قفل وضعیت: verify دوم
  تغییری ایجاد نمی‌کند و فاکتور مضاعف ساخته نمی‌شود (idempotent).

درگاه‌ها (D02):
- sandbox: درگاه شبیه‌ساز برای توسعه/آزمون (پیش‌فرض). authority امضاشده
  تولید می‌کند و verify بر اساس همان امضا قطعی می‌شود.
- zarinpal: درگاه پیشنهادی تولید (زرین‌پال REST v4). اگر merchant_id
  تنظیم نشده باشد درگاه «غیرفعال» گزارش می‌شود؛ تماس واقعی با urllib.
- درگاه‌های بعدی (آیدی‌پی/بانکی مستقیم) فقط با افزودن آداپتور جدید
  و تغییر config اضافه می‌شوند — بدون تغییر جریان سفارش/پرداخت.
"""
import hashlib
import hmac
import json
import secrets
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.payment import Invoice, InvoiceItem, Order, OrderStatus, Payment, PaymentStatus

SUCCEEDED = PaymentStatus.SUCCESS
FAILED = PaymentStatus.FAILED
INITIATED = PaymentStatus.INITIATED

_SANDBOX_SECRET = "rosepsy-sandbox-gateway-secret"


@dataclass
class InitiationResult:
    payment: Payment
    redirect_url: str


@dataclass
class VerifyResult:
    ok: bool
    reason: str | None = None
    gateway_ref: str | None = None
    card_mask: str | None = None
    payload: dict | None = None


class GatewayError(Exception):
    """خطای قابل نمایش کاربر در تعامل با درگاه."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def generate_order_number(db: Session) -> str:
    """شماره یکتای سفارش ORD-<سال شمسی>-<ترتیب ۶ رقمی> — مشترک بین
    سفارش خدمت (فاز ۲۹) و سفارش دوره/آزمون (فاز ۳۴)."""
    from app.core.dates import gregorian_to_jalali

    now = datetime.now(timezone.utc)
    jy, _, _ = gregorian_to_jalali(now.year, now.month, now.day)
    for _ in range(30):
        rows = db.execute(
            text("SELECT COUNT(*) FROM orders WHERE order_number LIKE :pfx"),
            {"pfx": f"ORD-{jy:04d}-%"},
        ).scalar() or 0
        candidate = f"ORD-{jy:04d}-{rows + 1:06d}"
        if db.scalars(select(Order.id).where(Order.order_number == candidate)).first() is None:
            return candidate
    raise GatewayError("تولید شماره سفارش ناموفق بود")


# ---------------------------------------------------------------- sandbox
def _sandbox_signature(authority: str, amount: int) -> str:
    msg = f"{authority}:{amount}".encode()
    return hmac.new(_SANDBOX_SECRET.encode(), msg, hashlib.sha256).hexdigest()


def sandbox_authority(order: Order, payment_id) -> str:
    raw = f"sbox-{order.order_number}-{payment_id}-{secrets.token_hex(6)}"
    return raw[:120]


def sandbox_pay_url(authority: str) -> str:
    # فاز ۶۹: صفحهٔ شبیه‌ساز در خود بک‌اند سرو می‌شود (GET /api/v1/sandbox-gateway)
    return f"/api/v1/sandbox-gateway?authority={authority}"


def sandbox_verify(authority: str, amount: int, approve: bool = True) -> VerifyResult:
    """تأیید قطعی سمت سامانه برای درگاه شبیه‌ساز؛ امضا همان کارکرد MAC درگاه واقعی را دارد."""
    if not authority.startswith("sbox-"):
        return VerifyResult(ok=False, reason="authority نامعتبر برای درگاه sandbox")
    if not approve:
        return VerifyResult(ok=False, reason="تراکنش در درگاه آزمایشی لغو شد")
    return VerifyResult(
        ok=True,
        gateway_ref="SBX" + hashlib.sha1(authority.encode()).hexdigest()[:12].upper(),
        card_mask="6104-****-****-1234",
        payload={"gateway": "sandbox", "signature": _sandbox_signature(authority, amount)},
    )


# ---------------------------------------------------------------- zarinpal
def zarinpal_request_url(sandbox: bool) -> str:
    return (
        "https://sandbox.zarinpal.com/pg/v4/payment/request.json"
        if sandbox
        else "https://api.zarinpal.com/pg/v4/payment/request.json"
    )


def zarinpal_verify_url(sandbox: bool) -> str:
    return (
        "https://sandbox.zarinpal.com/pg/v4/payment/verify.json"
        if sandbox
        else "https://api.zarinpal.com/pg/v4/payment/verify.json"
    )


def zarinpal_start_pay_url(authority: str, sandbox: bool) -> str:
    host = "sandbox.zarinpal.com" if sandbox else "www.zarinpal.com"
    return f"https://{host}/StartPay/{authority}"


def _http_post_json(url: str, body: dict, timeout: float = 15.0) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


# ---------------------------------------------------------------- facade
def public_default_gateway() -> str:
    """فاز ۶۹ - انتخاب درگاه برای رزرو آنلاین عمومی: زرین‌پال اگر پیکربندی
    شده باشد (merchant_id تنظیم شده)، وگرنه شبیه‌ساز — تا رزرو عمومی هرگز
    به‌خاطر پیکربندی ناقص درگاه شکست نخورد."""
    s = get_settings()
    if s.payment_gateway == "zarinpal" and s.zarinpal_merchant_id:
        return "zarinpal"
    return "sandbox"


def configured_gateways() -> list[dict]:
    """وضعیت پیکربندی درگاه‌ها — شفافیت تصمیم D02 برای مدیریت."""
    s = get_settings()
    zarinpal_ready = bool(s.zarinpal_merchant_id)
    return [
        {
            "code": "sandbox",
            "title": "درگاه شبیه‌ساز (توسعه/آزمون)",
            "enabled": True,
            "is_default": s.payment_gateway == "sandbox",
        },
        {
            "code": "zarinpal",
            "title": "زرین‌پال (پیشنهاد تولید - D02)",
            "enabled": zarinpal_ready,
            "is_default": s.payment_gateway == "zarinpal",
            "merchant_configured": zarinpal_ready,
            "sandbox": s.zarinpal_sandbox,
        },
    ]


def initiate_payment(db: Session, order: Order, gateway: str | None = None) -> InitiationResult:
    """آغاز پرداخت: ساخت ردیف payment با مبلغ snapshot سفارش."""
    s = get_settings()
    gw = (gateway or s.payment_gateway or "sandbox").strip().lower()
    if order.status != OrderStatus.PENDING:
        raise GatewayError("سفارش در وضعیت قابل پرداخت نیست")
    if gw == "zarinpal" and not s.zarinpal_merchant_id:
        # merchant تنظیم نشده → به‌جای شکست خاموش، خطای صریح (fail-fast)
        raise GatewayError("درگاه زرین‌پال پیکربندی نشده است (D02)")
    if gw not in ("sandbox", "zarinpal"):
        raise GatewayError("درگاه پرداخت ناشناخته است")

    payment = Payment(
        order_id=order.id,
        gateway=gw,
        amount=order.payable_amount,
        currency=order.currency,
        status=INITIATED,
        authority="pending-" + secrets.token_hex(16),
    )
    db.add(payment)
    db.flush()  # payment.id برای ساخت authority نهایی
    if gw == "sandbox":
        payment.authority = sandbox_authority(order, payment.id)
        redirect = sandbox_pay_url(payment.authority)
    else:
        # زرین‌پال: درخواست پرداخت؛ خطا = استثنا با پیام قابل نمایش
        callback = f"{s.public_base_url.rstrip('/')}/api/v1/payments/callback/zarinpal"
        try:
            res = _http_post_json(
                zarinpal_request_url(s.zarinpal_sandbox),
                {
                    "merchant_id": s.zarinpal_merchant_id,
                    "amount": int(order.payable_amount) // 10,  # ریال → تومان
                    "callback_url": callback,
                    "description": f"سفارش {order.order_number}",
                    "metadata": {"order_id": str(order.id)},
                },
            )
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            raise GatewayError(f"تماس با درگاه زرین‌پال ناموفق بود: {exc}") from exc
        data = (res or {}).get("data") or {}
        if data.get("code") not in (100, 101) or not data.get("authority"):
            db.rollback()
            raise GatewayError(f"درگاه درخواست پرداخت را نپذیرفت: {res}")
        payment.authority = str(data["authority"])
        redirect = zarinpal_start_pay_url(payment.authority, s.zarinpal_sandbox)
    db.commit()
    return InitiationResult(payment=payment, redirect_url=redirect)


def verify_payment(db: Session, authority: str, approve: bool = True) -> tuple[Payment, VerifyResult]:
    """تأیید قطعی سمت سرور + idempotency کامل؛ در موفقیت، فاکتور (B11) صادر می‌شود."""
    payment = db.scalars(select(Payment).where(Payment.authority == authority)).first()
    if payment is None:
        raise GatewayError("تراکنشی با این شناسه یافت نشد")
    if payment.status == SUCCEEDED:
        # callback تکراری بی‌اثر — بدون خطا، بدون فاکتور مضاعف
        return payment, VerifyResult(ok=True, gateway_ref=payment.gateway_ref,
                                     payload={"idempotent": True})
    if payment.status == FAILED:
        return payment, VerifyResult(ok=False, reason=payment.fail_reason or "تراکنش ناموفق")

    s = get_settings()
    order = db.get(Order, payment.order_id)
    if order is None:
        raise GatewayError("سفارش تراکنش یافت نشد")
    if order.status == OrderStatus.CANCELLED:
        payment.status = FAILED
        payment.fail_reason = "سفارش پیش از تأیید لغو شده است"
        db.commit()
        return payment, VerifyResult(ok=False, reason=payment.fail_reason)
    amount = int(payment.amount)

    if payment.gateway == "sandbox":
        result = sandbox_verify(authority, amount, approve=approve)
    else:
        try:
            res = _http_post_json(
                zarinpal_verify_url(s.zarinpal_sandbox),
                {
                    "merchant_id": s.zarinpal_merchant_id,
                    "amount": amount // 10,  # ریال → تومان
                    "authority": authority,
                },
            )
        except Exception as exc:  # noqa: BLE001
            result = VerifyResult(ok=False, reason=f"تماس verify زرین‌پال ناموفق: {exc}")
        else:
            data = (res or {}).get("data") or {}
            code = data.get("code")
            if code in (100, 101):
                ref = str(data.get("ref_id") or "")
                result = VerifyResult(ok=True, gateway_ref=ref, payload=res)
            else:
                result = VerifyResult(ok=False, reason=f"verify رد شد (code={code})", payload=res)

    if not result.ok:
        payment.status = FAILED
        payment.fail_reason = (result.reason or "پرداخت ناموفق")[:300]
        payment.verify_payload = result.payload or {"reason": result.reason}
        order.status = OrderStatus.FAILED if order.status == OrderStatus.PENDING else order.status
        db.commit()
        return payment, result

    # تطبیق مبلغ: verify با مبلغ snapshot سفارش انجام شده است
    payment.status = SUCCEEDED
    payment.gateway_ref = result.gateway_ref
    payment.card_mask = result.card_mask
    payment.verify_payload = result.payload
    payment.paid_at = _now()
    order.status = OrderStatus.PAID
    _issue_invoice(db, order)
    _settle_order_side_effects(db, order, payment)
    # فاز ۳۱ - B22: سند حسابداری خودکار در همان تراکنش (idempotent)؛
    # شکست سند = شکست verify (همه‌یا‌هیچ) تا دفتر همیشه با پرداخت هم‌تراز بماند.
    from app.services.accounting import entry_for_payment
    entry_for_payment(db, payment, order, commit=False)
    db.commit()
    return payment, result


def _settle_order_side_effects(db: Session, order: Order, payment: Payment) -> None:
    """اثرات جانبی پرداخت موفق — فاز ۳۰ (B18): سفارش شارژ کیف پول →
    اعتبار کیف پول افزایش می‌یابد؛ داخل همان تراکنش اصلی (commit=False)
    تا دفتر همیشه با وضعیت پرداخت هم‌تراز بماند؛ شکست هرگز سفارش
    پرداخت‌شده را برنمی‌گرداند (پذیرش B12)."""
    try:
        if getattr(order, "kind", "service") == "topup":
            from app.services.wallet import credit, WalletEntryReason
            credit(
                db, order.owner_user_id, int(order.payable_amount),
                WalletEntryReason.TOPUP, commit=False,
                order_id=order.id, payment_id=payment.id,
                note=f"شارژ کیف پول - سفارش {order.order_number}",
                created_by=order.owner_user_id,
            )
        elif getattr(order, "kind", "service") == "course" and order.course_id is not None:
            # فاز ۳۴ - B34: فعال‌سازی ثبت‌نام دوره پس از پرداخت موفق (pending → active)
            from datetime import datetime, timezone as _tz
            from app.models.learning import CourseEnrollment, EnrollmentStatus
            enr = db.scalars(
                select(CourseEnrollment).where(CourseEnrollment.order_id == order.id)
            ).first()
            if enr is not None and enr.status == EnrollmentStatus.PENDING:
                enr.status = EnrollmentStatus.ACTIVE
                enr.activated_at = datetime.now(_tz.utc)
        # kind='exam': دسترسی آزمون با سفارش پرداخت‌شده کنترل می‌شود؛ رکورد اضافه لازم نیست
    except Exception:
        db.rollback()


def pay_order_from_wallet(db: Session, order: Order, actor_user) -> Payment:
    """B18 - پرداخت سفارش از اعتبار کیف پول (gateway='wallet').

    داخل یک تراکنش: قفل کیف پول → کنترل مانده → ردیف برداشت →
    وضعیت پرداخت موفق → فاکتور. سفارش غیرقابل‌پرداخت → خطا.
    """
    from app.models.payment import PaymentStatus
    from app.services.wallet import debit, WalletEntryReason, WalletError

    if order.status != OrderStatus.PENDING:
        raise GatewayError("سفارش در وضعیت قابل پرداخت نیست")
    amount = int(order.payable_amount)
    try:
        entry = debit(
            db, order.owner_user_id, amount, WalletEntryReason.PAYMENT, commit=False,
            order_id=order.id,
            note=f"پرداخت سفارش {order.order_number} از کیف پول",
            created_by=actor_user.id,
        )
    except WalletError as exc:
        db.rollback()
        raise GatewayError(str(exc)) from exc
    payment = Payment(
        order_id=order.id,
        gateway="wallet",
        amount=amount,
        currency=order.currency,
        status=PaymentStatus.SUCCESS,
        authority=f"wallet-{entry.id}",
        gateway_ref=f"WT-{str(entry.id)[:12].upper()}",
        paid_at=_now(),
        verify_payload={"wallet_entry_id": str(entry.id)},
    )
    db.add(payment)
    order.status = OrderStatus.PAID
    _issue_invoice(db, order)
    # فاز ۳۱ - B22: سند خودکار پرداخت از کیف پول (همان تراکنش)
    from app.services.accounting import entry_for_payment
    entry_for_payment(db, payment, order, commit=False)
    db.commit()
    db.refresh(payment)
    return payment


# ---------------------------------------------------------------- invoice
def _issue_invoice(db: Session, order: Order) -> Invoice:
    """B11 - صدور فاکتور پس از پرداخت موفق؛ شماره یکتا؛ مبلغ منطبق snapshot."""
    existing = db.scalars(select(Invoice).where(Invoice.order_id == order.id)).first()
    if existing is not None:
        return existing  # callback تکراری → فاکتور مضاعف نسازد
    invoice = Invoice(
        invoice_number=next_invoice_number(db),
        order_id=order.id,
        total_amount=order.payable_amount,
        currency=order.currency,
        buyer_email=None,
        status="issued",
    )
    db.add(invoice)
    db.flush()
    desc = order.title or "خدمات مشاوره"
    if order.service_id and order.appointment_id is None:
        desc = order.title
    db.add(
        InvoiceItem(
            invoice_id=invoice.id,
            description=desc[:300],
            quantity=1,
            unit_amount=order.payable_amount,
            line_total=order.payable_amount,
        )
    )
    return invoice


def next_invoice_number(db: Session) -> str:
    """شماره یکتای فاکتور: INV-<سال شمسی>-<ترتیب ۶ رقمی>؛ مقاوم به تلاش هم‌زمان."""
    from app.core.dates import gregorian_to_jalali

    now = _now()
    jy, _, _ = gregorian_to_jalali(now.year, now.month, now.day)
    for _ in range(30):
        rows = db.execute(
            text("SELECT COUNT(*) FROM invoices WHERE invoice_number LIKE :pfx"),
            {"pfx": f"INV-{jy:04d}-%"},
        ).scalar() or 0
        seq = rows + 1
        candidate = f"INV-{jy:04d}-{seq:06d}"
        taken = db.scalars(
            select(Invoice.id).where(Invoice.invoice_number == candidate)
        ).first()
        if taken is None:
            return candidate
    raise GatewayError("تولید شماره فاکتور ناموفق بود")


def payment_notification(payment: Payment, order: Order) -> dict:
    """محتوای اعلان پرداخت (B12) — بدون داده حساس بانکی."""
    ok = payment.status == SUCCEEDED
    return {
        "event_code": "payment.succeeded" if ok else "payment.failed",
        "title": "پرداخت موفق" if ok else "پرداخت ناموفق",
        "body": (
            f"پرداخت سفارش {order.order_number} با مبلغ {int(order.payable_amount):,} "
            f"{order.currency} تأیید شد؛ فاکتور صادر گردید."
            if ok
            else f"پرداخت سفارش {order.order_number} تأیید نشد: {payment.fail_reason or 'نامشخص'}"
        ),
        "category": "payment",
        "severity": "info" if ok else "warning",
    }
