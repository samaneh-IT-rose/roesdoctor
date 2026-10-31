"""فاز ۶۹ - نظرسنجی و امتیازدهی مشاوران (الگوی اسنپ‌داکتر).

قواعد:
- فقط کاربری که رزرو پرداخت‌شده (payment_status='paid') برای آن مشاور
  دارد می‌تواند نظر ثبت کند؛ توکن دعوت (review_token) صرفاً پس از تأیید
  قطعی پرداخت سمت سرور صادر می‌شود و در URL بازگشت از درگاه به کاربر
  داده می‌شود (قابلیت اثبات بدون احراز هویت).
- برای هر رزرو حداکثر یک نظر (unique consultation_request_id).
- نمایش عمومی فقط نظرات is_published=True.
- امتیاز ۱ تا ۵ ستاره + متن نظر اختیاری.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CounselorReview(Base):
    """نظر/امتیاز کاربر دربارهٔ یک مشاور پس از رزرو پرداخت‌شده."""

    __tablename__ = "counselor_reviews"
    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_counselor_reviews_rating"),
        Index("ix_counselor_reviews_counselor_published", "counselor_id", "is_published"),
        Index("ix_counselor_reviews_author", "author_user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    counselor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("counselors.id", ondelete="CASCADE"), nullable=False
    )
    # اگر رزرو با حساب کاربر خودکار (فاز ۶۹) انجام شده باشد پر می‌شود
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # هر رزرو حداکثر یک نظر
    consultation_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consultation_requests.id", ondelete="SET NULL"),
        nullable=True, unique=True,
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
