"""فاز ۲۹ - B10/B11 سند جامع: سفارش، پرداخت و فاکتور.

B10 - سفارش/پرداخت:
- سفارش از snapshot قیمت نوبت (فاز ۲۸، B07) ساخته می‌شود؛ مبلغ سفارش
  پس از ساخت با تغییر تعرفه تغییر نمی‌کند.
- فاز ۳۴: kind ها extends شدند ('service','topup','course','exam')؛
  سفارش دوره/آزمون course_id/exam_id دارد (فاز ۳۴).
- پرداخت فقط پس از «تأیید قطعی سمت سرور» موفق می‌شود (verify server-side)؛
  callback تکراری بی‌اثر است (idempotent با authority یکتا).

B11 - فاکتور:
- پس از اولین پرداخت موفق هر سفارش، دقیقاً یک فاکتور با شماره یکتا
  ساخته می‌شود؛ مبلغ فاکتور با snapshot سفارش منطبق است.

تصمیم D02 (درگاه پرداخت): معماری درگاه پلاگین‌پذیر؛
- «sandbox» برای توسعه/آزمون (پیش‌فرض)،
- «zarinpal» درگاه پیشنهادی تولید (زرین‌پال REST v4)؛
  تعویض درگاه صرفاً با تنظیمات PAYMENT_GATEWAY انجام می‌شود.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OrderStatus:
    PENDING = "pending"
    PAID = "paid"
    CANCELLED = "cancelled"
    FAILED = "failed"
    ALL = (PENDING, PAID, CANCELLED, FAILED)


class PaymentStatus:
    INITIATED = "initiated"
    SUCCESS = "success"
    FAILED = "failed"
    ALL = (INITIATED, SUCCESS, FAILED)


class InvoiceStatus:
    ISSUED = "issued"
    VOID = "void"
    ALL = (ISSUED, VOID)


class Order(Base):
    """B10 - سفارش خدمت با snapshot مبلغ؛ مرجع پرداخت و فاکتور."""

    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("status IN ('pending','paid','cancelled','failed')", name="ck_orders_status"),
        CheckConstraint("amount >= 0", name="ck_orders_amount_nonneg"),
        CheckConstraint("discount_amount IS NULL OR discount_amount >= 0", name="ck_orders_discount_nonneg"),
        CheckConstraint("payable_amount >= 0", name="ck_orders_payable_nonneg"),
        CheckConstraint("kind IN ('service','topup','course','exam')", name="ck_orders_kind"),
        CheckConstraint("refunded_amount >= 0", name="ck_orders_refunded_nonneg"),
        CheckConstraint("org_share_amount IS NULL OR org_share_amount >= 0",
                        name="ck_orders_org_share_nonneg"),
        Index("ix_orders_owner", "owner_user_id"),
        Index("ix_orders_status", "status"),
        Index("ix_orders_appointment", "appointment_id"),
        Index("ix_orders_organization", "organization_id"),
        Index("ix_orders_consultation_request", "consultation_request_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_number: Mapped[str] = mapped_column(String(40), unique=True)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="SET NULL"), nullable=True
    )
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appointments.id", ondelete="SET NULL"),
        nullable=True, unique=True,
    )
    service_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id", ondelete="RESTRICT"), nullable=True
    )
    tariff_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tariff_versions.id", ondelete="RESTRICT"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(300))
    # snapshot قیمت (از تعرفه لحظه ثبت نوبت/سفارش) - B07: قیمت گذشته تغییر نکند
    amount: Mapped[int] = mapped_column(Numeric(16, 2))
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    discount_amount: Mapped[int | None] = mapped_column(Numeric(16, 2), nullable=True)
    payable_amount: Mapped[int] = mapped_column(Numeric(16, 2))
    status: Mapped[str] = mapped_column(String(20), default=OrderStatus.PENDING)
    # فاز ۳۰ - B18/B19: نوع سفارش + مرجع کد تخفیف + استرداد اجراشده
    kind: Mapped[str] = mapped_column(String(20), default="service")  # service / topup
    discount_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discounts.id", ondelete="RESTRICT"), nullable=True
    )
    refunded_amount: Mapped[int] = mapped_column(Numeric(16, 2), default=0)
    # فاز ۳۴ - B34/B35: سفارش ثبت‌نام دوره / دسترسی آزمون (بدون نوبت)
    course_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="RESTRICT"), nullable=True
    )
    exam_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exams.id", ondelete="RESTRICT"), nullable=True
    )
    # فاز ۳۳ - B21: تقسیم سهم پرداخت سازمان — snapshot در لحظه ساخت سفارش
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    # فاز ۶۹ - سفارش پرداخت آنلاین رزرو عمومی (اتصال به درخواست مشاوره)
    consultation_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consultation_requests.id", ondelete="SET NULL"),
        nullable=True, unique=True,
    )
    contract_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="RESTRICT"), nullable=True
    )
    coverage_percent: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    org_share_amount: Mapped[int | None] = mapped_column(Numeric(16, 2), nullable=True)
    applicant_share_amount: Mapped[int | None] = mapped_column(Numeric(16, 2), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Payment(Base):
    """B10 - تلاش پرداخت در درگاه؛ تأیید قطعی سمت سرور و callback تکراری بی‌اثر.

    authority شناسه یکتای تراکنش سمت سامانه است که به درگاه داده می‌شود؛
    gateway_ref شناسه/رسید سمت درگاه پس از بازگشت.
    """

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("status IN ('initiated','success','failed')", name="ck_payments_status"),
        CheckConstraint("amount >= 0", name="ck_payments_amount_nonneg"),
        Index("ix_payments_order", "order_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False
    )
    gateway: Mapped[str] = mapped_column(String(30))
    amount: Mapped[int] = mapped_column(Numeric(16, 2))
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    status: Mapped[str] = mapped_column(String(20), default=PaymentStatus.INITIATED)
    authority: Mapped[str] = mapped_column(String(120), unique=True)
    gateway_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    card_mask: Mapped[str | None] = mapped_column(String(30), nullable=True)
    fail_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    verify_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Invoice(Base):
    """B11 - فاکتور سفارش با شماره یکتا؛ مبلغ با snapshot سفارش منطبق."""

    __tablename__ = "invoices"
    __table_args__ = (
        CheckConstraint("status IN ('issued','void')", name="ck_invoices_status"),
        CheckConstraint("total_amount >= 0", name="ck_invoices_total_nonneg"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_number: Mapped[str] = mapped_column(String(40), unique=True)
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    total_amount: Mapped[int] = mapped_column(Numeric(16, 2))
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    buyer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    buyer_national_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    buyer_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=InvoiceStatus.ISSUED)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InvoiceItem(Base):
    """B11 - ردیف فاکتور؛ خط_total = quantity × unit_amount."""

    __tablename__ = "invoice_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_invoice_items_qty_positive"),
        CheckConstraint("unit_amount >= 0", name="ck_invoice_items_unit_nonneg"),
        Index("ix_invoice_items_invoice", "invoice_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=False
    )
    description: Mapped[str] = mapped_column(String(300))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_amount: Mapped[int] = mapped_column(Numeric(16, 2))
    line_total: Mapped[int] = mapped_column(Numeric(16, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
