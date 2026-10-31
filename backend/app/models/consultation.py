import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, func,
)
from sqlalchemy.schema import Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ConsultPaymentStatus:
    """فاز ۶۹: وضعیت پرداخت آنلاین رزرو (درگاه زرین‌پال/شبیه‌ساز)."""

    NOT_REQUIRED = "not_required"  # رزرو بدون پرداخت آنلاین (جریان قدیمی)
    PENDING = "pending"            # سفارش ساخته شده، منتظر تأیید درگاه
    PAID = "paid"                  # تأیید قطعی سمت سرور انجام شد
    FAILED = "failed"              # درگاه پرداخت را تأیید نکرد
    ALL = (NOT_REQUIRED, PENDING, PAID, FAILED)


class ConsultationRequest(Base):
    """درخواست مشاوره از سایت عمومی (فاز ۱۰) - فاز ۲۱: رزرو اسلات"""

    __tablename__ = "consultation_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('new','in_review','converted','archived')",
            name="ck_consult_status",
        ),
        CheckConstraint(
            "payment_status IN ('not_required','pending','paid','failed')",
            name="ck_consult_payment_status",
        ),
        Index("ix_consult_payment_status", "payment_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(String(200))
    mobile: Mapped[str] = mapped_column(String(20))
    topic: Mapped[str] = mapped_column(String(100))
    preferred_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    preferred_slot: Mapped[str | None] = mapped_column(String(30), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="new")
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    handled_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applicant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applicants.id", ondelete="SET NULL"), nullable=True
    )
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="SET NULL"), nullable=True
    )
    reception_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_attempts: Mapped[int] = mapped_column(Integer, default=0)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    referral_source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # فاز ۲۱ - رزرو آنلاین اسلات
    preferred_counselor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("counselors.id", ondelete="SET NULL"), nullable=True
    )
    preferred_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # فاز ۲۸ - B06: خدمت انتخابی درخواست (غیرفعال قابل انتخاب نیست)
    service_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id", ondelete="SET NULL"), nullable=True
    )
    # فاز ۶۹ - پرداخت آنلاین رزرو (زرین‌پال) + توکن دعوت به ثبت نظر
    payment_status: Mapped[str] = mapped_column(String(20), default=ConsultPaymentStatus.NOT_REQUIRED)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_token: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())