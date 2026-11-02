import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Table, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.rbac import role_permissions_table

# بند ۳.۱ سند - نقش‌های نسخه اولیه (DPO: فاز ۲۷ - حسابرس حفاظت داده)
ROLE_CODES: dict[str, str] = {
    "SYSTEM_ADMIN": "مدیر سامانه",
    "ORG_MANAGER": "مدیر سازمان",
    "RECEPTION": "پذیرش",
    "COUNSELOR": "مشاور",
    "TECHNICAL_SUPERVISOR": "مسئول فنی",
    "APPLICANT": "متقاضی",
    "DPO": "حسابرس حفاظت داده (DPO)",
}

# نقش‌های سیستمی - قابل حذف نیستند و ماتریسشان در رابط گرافیکی قابل ویرایش است
# ولی حذف نقش/تغییر کد آن مجاز نیست (فاز ۵۲)
SYSTEM_ROLE_CODES = set(ROLE_CODES.keys())


class UserStatus:
    PENDING = "pending_activation"
    ACTIVE = "active"
    DISABLED = "disabled"


user_roles_table = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_code", String(50), ForeignKey("roles.code", ondelete="RESTRICT"), primary_key=True),
)


class Role(Base):
    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    # فاز ۵۲: سطح دسترسی روی داده (all/own/assigned) - پیش‌فرض همهٔ داده‌ها
    data_scope: Mapped[str] = mapped_column(String(20), default="all", server_default="all")

    # فاز ۵۲: ماتریس دسترسی نقش - کاتالوگ در app.models.rbac
    permissions: Mapped[list["Permission"]] = relationship(
        "Permission",
        secondary=role_permissions_table,
        lazy="selectin",
    )


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("status IN ('pending_activation','active','disabled')", name="ck_users_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(20), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default=UserStatus.PENDING)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    auth_version: Mapped[int] = mapped_column(Integer, default=1)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # فاز ۷۴ - ایزولاسیون دادهٔ سازمانی: هر کاربر (مدیر سازمان، پذیرش، مشاور،
    # متقاضی و …) می‌تواند به یک سازمان منتسب شود تا فقط اطلاعات همان سازمان
    # را ببیند. NULL = بدون محدودیت (رفتار قبلی - مدیران سامانه).
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    roles: Mapped[list[Role]] = relationship("Role", secondary=user_roles_table, lazy="selectin")


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(400), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ActivationToken(Base):
    __tablename__ = "activation_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
