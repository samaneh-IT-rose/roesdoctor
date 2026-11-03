"""فاز ۳۳ - B21 سند جامع: سازمان‌ها، قراردادها و سهم پرداخت.

- سازمان (کارفرما/کارگزار) با slug یکتا؛ متقاضی می‌تواند به یک سازمان
  منتسب شود (applicants.organization_id)؛
- قرارداد: درصد سهم سازمان (۰ < p ≤ ۱۰۰) + سقف اختیاری مبلغ سهم به‌ازای
  هر سفارش + بازه اعتبار + وضعیت draft/active/terminated؛
- دامنه خدمت قرارداد: بدون ردیف = همه خدمات؛ با ردیف = فقط همان خدمات؛
- پذیرش سند: تقسیم سهم در لحظه ساخت سفارش snapshot می‌شود (سهم سازمان و
  سهم متقاضی) و با تغییر/لغو قرارداد بعدی تغییر نمی‌کند؛ قرارداد و تخفیف
  هم‌زمان قابل استفاده نیستند (منع دو‌جبری شدن هزینه)؛
- سهم سازمانِ سفارش‌های پرداخت‌شده «مطالبه از سازمان» گزارش می‌شود؛
  چرخه صورتحساب سازمان (دوره‌ای) خارج از دامنه این فاز است.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Organization(Base):
    """B21 - سازمان کارفرما/کارگزار با شناسه عمومی یکتا."""

    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    national_id: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # فاز ۷۵ — برندینگ آزمون سازمانی (صفحه ورودی/اجرای آزمون کارکنان)
    brand_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    brand_logo_path: Mapped[str | None] = mapped_column(String(300), nullable=True)  # زیر uploads/org_logos
    entry_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    entry_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Contract(Base):
    """B21 - قرارداد سازمان: سهم پرداخت سازمان با بازه اعتبار و وضعیت."""

    __tablename__ = "contracts"
    __table_args__ = (
        CheckConstraint("status IN ('draft','active','terminated')", name="ck_contracts_status"),
        CheckConstraint("coverage_percent > 0 AND coverage_percent <= 100",
                        name="ck_contracts_percent_range"),
        CheckConstraint("coverage_cap_amount IS NULL OR coverage_cap_amount >= 0",
                        name="ck_contracts_cap_nonneg"),
        CheckConstraint("valid_to IS NULL OR valid_to >= valid_from",
                        name="ck_contracts_date_range"),
        Index("ix_contracts_org", "organization_id"),
        Index("ix_contracts_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200))
    coverage_percent: Mapped[float] = mapped_column(Numeric(5, 2))
    coverage_cap_amount: Mapped[int | None] = mapped_column(Numeric(16, 2), nullable=True)
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    organization: Mapped["Organization"] = relationship(lazy="joined")


class ContractService(Base):
    """B21 - دامنه خدمت قرارداد؛ بدون ردیف = همه خدمات."""

    __tablename__ = "contract_services"
    __table_args__ = (
        UniqueConstraint("contract_id", "service_id", name="uq_contract_service"),
        Index("ix_contract_services_contract", "contract_id"),
        Index("ix_contract_services_service", "service_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="RESTRICT"), nullable=False
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ContractTest(Base):
    """فاز ۶۲ - دامنه آزمون روان‌شناسی قرارداد؛ بدون ردیف = همه آزمون‌ها باز.

    مدیر در قرارداد سازمان مشخص می‌کند کدام آزمون‌ها برای آن سازمان باز باشد؛
    نمایش «آزمون‌های باز سازمان» از قرارداد فعال مشتق می‌شود.
    """

    __tablename__ = "contract_tests"
    __table_args__ = (
        UniqueConstraint("contract_id", "test_id", name="uq_contract_test"),
        Index("ix_contract_tests_contract", "contract_id"),
        Index("ix_contract_tests_test", "test_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="RESTRICT"), nullable=False
    )
    test_id: Mapped[uuid.UUID] = mapped_column(
        # رفرش با نام جدول برای پرهیز از وابستگی حلقوی به مدل PsychTest
        UUID(as_uuid=True), ForeignKey("psych_tests.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
