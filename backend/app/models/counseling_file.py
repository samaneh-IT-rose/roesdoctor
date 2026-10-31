"""فاز ۷۰ - پروندهٔ مشاورهٔ هر کاربر (User Counseling File).

- برای «هر کاربر» یک پروندهٔ مشاوره ساخته می‌شود (به‌صورت خودکار با اولین
  آزمون یا اولین رزرو/درخواست مشاوره) و در آن تاریخچهٔ آزمون‌ها و مشاوره‌های
  انجام‌شده به همراه زمانشان نگهداری می‌شود (timeline از جداول منبع خوانده
  می‌شود — بدون کپی داده؛ جدول فقط هویت و جمع‌بندی فعالیت را نگه می‌دارد).
- خودِ اقلام خط زمانی:
  * psych_attempts (آزمون‌ها — نمره/تفسیر/زمان + viewed_at)
  * consultation_requests (درخواست/رزروهای مشاوره — از طریق اتصال
    applicant.user_id یا تطابق موبایل)
  * appointments (نوبت‌های پرونده‌های همان کاربر)
- staff می‌تواند از پنل «پرونده‌های مشاوره» فهرست و جزئیات را ببیند و از
  روی آزمونِ هر کاربر برایش پروندهٔ بالینی (cases) بسازد.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

FILE_CODE_MAX = 30


class UserCounselingFile(Base):
    """فاز ۷۰ - پروندهٔ مشاورهٔ کاربر (یک ردیف یکتا برای هر user)."""

    __tablename__ = "user_counseling_files"
    __table_args__ = (
        Index("ix_ucf_updated", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    # شمارهٔ پروندهٔ مشاوره — یکتا و قابل جست‌وجو (UF = User File)
    file_code: Mapped[str] = mapped_column(String(FILE_CODE_MAX), unique=True, nullable=False)
    # یادداشت داخلی پذیرش/مشاور دربارهٔ این پرونده (اختیاری)
    staff_note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
