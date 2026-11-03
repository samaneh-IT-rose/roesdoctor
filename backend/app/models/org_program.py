"""فاز ۵۸ - پنل آزمون‌های سازمانی (برنامهٔ ارزیابی سازمانی).

الگو: هر سازمان (مثلاً «شرکت نفت پارس») می‌تواند چند «برنامهٔ آزمون»
(پروژهٔ ارزیابی) داشته باشد که شامل:
- آزمون‌های موردنیاز از بانک آزمون‌های مرکز آزمون (PsychTest منتشرشده)؛
- اعضا/کارکنان سازمان (با کد پرسنلی، واحد سازمانی و در صورت وجود
  حساب کاربری، پیوند به user برای پیگیری پیشرفت)؛
- مشاوران پروژه (کاربران دارای نقش مشاور) که در کارتابل برنامه
  قابل گفتگوی آنلاین هستند؛
- راهنمای پروژه و سوالات پرتکرار (FAQ)؛
- کارتابل برنامه: نمای تجمیعی تست‌ها + مشاوران + راهنما + FAQ +
  پیشرفت هر عضو (تعداد آزمون‌های تکمیل‌شده از PsychAttempt).
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
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OrgProgramStatus:
    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"
    ALL = (DRAFT, ACTIVE, CLOSED)


class OrgProgram(Base):
    """فاز ۵۸ - برنامهٔ آزمون سازمانی (پروژهٔ ارزیابی) برای یک سازمان."""

    __tablename__ = "org_programs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','active','closed')",
            name="ck_org_programs_status",
        ),
        Index("ix_org_programs_org", "organization_id"),
        Index("ix_org_programs_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # راهنمای پروژه — متن راهنمای شرکت‌کنندگان (HTML ساده/متن)
    guide_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=OrgProgramStatus.ACTIVE)
    # مهلت انجام آزمون‌ها (اختیاری)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class OrgProgramTest(Base):
    """فاز ۵۸ - آزمون‌های منتخب برنامه از بانک آزمون‌های مرکز آزمون."""

    __tablename__ = "org_program_tests"
    __table_args__ = (
        UniqueConstraint("program_id", "test_id", name="uq_org_program_test"),
        Index("ix_org_program_tests_program", "program_id"),
        Index("ix_org_program_tests_test", "test_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    program_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("org_programs.id", ondelete="CASCADE"), nullable=False
    )
    test_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("psych_tests.id", ondelete="RESTRICT"), nullable=False
    )
    # آزمون الزامی یا اختیاری برای اعضا
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # فاز ۷۵ — عنوان نمایشی آزمون برای شرکت‌کنندگان این برنامه
    # (مثلاً «ارزیابی سلامت کارکنان» به‌جای نام بالینی ابزار)؛ NULL = عنوان اصلی
    display_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrgProgramMember(Base):
    """فاز ۵۸ - عضو (کارمند) سازمان در برنامهٔ آزمون.

    user_id اختیاری است: اگر عضو حساب کاربری فعال در سامانه داشته باشد،
    پیشرفت او (تکمیل آزمون‌ها) از PsychAttempt پیگیری می‌شود؛ در غیر این
    صورت عضو فقط در فهرست سازمان ثبت می‌شود و پذیرش می‌تواند بعداً حساب
    را پیوند بزند.
    """

    __tablename__ = "org_program_members"
    __table_args__ = (
        UniqueConstraint("program_id", "user_id", name="uq_org_program_member_user"),
        Index("ix_org_program_members_program", "program_id"),
        Index("ix_org_program_members_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    program_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("org_programs.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    full_name: Mapped[str] = mapped_column(String(200))
    employee_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(30), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(120), nullable=True)  # واحد سازمانی
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrgProgramCounselor(Base):
    """فاز ۵۸ - مشاوران پروژه؛ در کارتابل برنامه با دکمهٔ چت آنلاین."""

    __tablename__ = "org_program_counselors"
    __table_args__ = (
        UniqueConstraint("program_id", "user_id", name="uq_org_program_counselor"),
        Index("ix_org_program_counselors_program", "program_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    program_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("org_programs.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    role_in_project: Mapped[str] = mapped_column(String(80), default="مشاور", server_default="مشاور")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrgProgramFaq(Base):
    """فاز ۵۸ - سوالات پرتکرار برنامه (راهنمای شرکت‌کنندگان)."""

    __tablename__ = "org_program_faqs"
    __table_args__ = (
        CheckConstraint("sort_order >= 0", name="ck_org_program_faqs_sort_nonneg"),
        Index("ix_org_program_faqs_program", "program_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    program_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("org_programs.id", ondelete="CASCADE"), nullable=False
    )
    question: Mapped[str] = mapped_column(String(500))
    answer: Mapped[str] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
