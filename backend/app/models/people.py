import uuid
from datetime import date, datetime, time

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OrganizationUnit(Base):
    __tablename__ = "organization_units"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organization_units.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ServiceLocation(Base):
    __tablename__ = "service_locations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UserScope(Base):
    __tablename__ = "user_scopes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organization_units.id", ondelete="SET NULL"), nullable=True
    )
    service_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service_locations.id", ondelete="SET NULL"), nullable=True
    )


class Counselor(Base):
    __tablename__ = "counselors"
    __table_args__ = (CheckConstraint("status IN ('active','inactive','suspended')", name="ck_counselors_status"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    counselor_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    national_id: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True, index=True)
    professional_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    degree: Mapped[str | None] = mapped_column(String(100), nullable=True)
    specialty: Mapped[str | None] = mapped_column(String(100), nullable=True)
    license_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    license_expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    license_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    work_mobile: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    service_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service_locations.id", ondelete="SET NULL"), nullable=True
    )
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    photo_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="active")
    # فاز ۶۴: فیلدهای پروندهٔ مشاور مطابق فایل ورود شرکت رز (قالب اکسل)
    province_code: Mapped[str | None] = mapped_column(
        String(2), ForeignKey("provinces.code", ondelete="SET NULL"), nullable=True
    )
    # فاز ۶۵: کلینک محل خدمت مشاور — از claim «clinic» توکن ورود یکپارچه رز هاب
    clinic: Mapped[str | None] = mapped_column(String(200), nullable=True)
    professional_rank: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contract_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sheba_number: Mapped[str | None] = mapped_column(String(34), nullable=True)
    detailed_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # فاز ۶۶ - شعبهٔ کلینیک (برای نمایش مشاوران هر کلینیک روی نقشهٔ سایت)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, unique=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CounselorAvailability(Base):
    """فاز ۷۴ - روزها و ساعت‌های مشاورهٔ هر مشاور.

    مشاور در کارتابل خودش (کارتابل مشاور) بازه‌های هفتگی‌اش را تعریف می‌کند؛
    پس از آن ثبت/جابه‌جایی نوبت و رزرو آنلاین فقط در همین بازه‌ها پذیرفته
    می‌شود. قرارداد weekday با ``date.weekday()`` یکسان است:
    دوشنبه=0 … یکشنبه=6 (شنبه=5، جمعه=4). اگر مشاور هیچ بازه‌ای تعریف
    نکرده باشد، رفتار قبلی (ساعت‌های پیش‌فرض سامانه) برقرار می‌ماند.
    """

    __tablename__ = "counselor_availabilities"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_counselor_availability_weekday"),
        CheckConstraint("end_time > start_time", name="ck_counselor_availability_range"),
        UniqueConstraint("counselor_id", "weekday", "start_time", name="uq_counselor_availability_slot"),
        Index("ix_counselor_availability_counselor", "counselor_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    counselor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("counselors.id", ondelete="CASCADE"), nullable=False
    )
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[time] = mapped_column(nullable=False)
    end_time: Mapped[time] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Applicant(Base):
    __tablename__ = "applicants"
    __table_args__ = (
        CheckConstraint("status IN ('active','inactive','archived')", name="ck_applicants_status"),
        CheckConstraint("record_source IN ('manual','excel')", name="ck_applicants_source"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True, index=True)
    employee_code: Mapped[str | None] = mapped_column(String(50), nullable=True, unique=True, index=True)
    national_id: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    marital_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    education: Mapped[str | None] = mapped_column(String(100), nullable=True)
    occupation: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(20), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organization_units.id", ondelete="SET NULL"), nullable=True
    )
    # فاز ۳۳ - B21: سازمان کارفرما/کارگزار متقاضی (مبنای قرارداد و سهم پرداخت)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    service_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service_locations.id", ondelete="SET NULL"), nullable=True
    )
    province_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    county_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    referral_source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    referral_description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="active")
    record_source: Mapped[str] = mapped_column(String(20), default="manual")
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, unique=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
