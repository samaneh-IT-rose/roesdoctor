"""فاز ۵۲ - مدیریت کاربران پیشرفته: نقش‌ها با ماتریس دسترسی گرافیکی.

طراحی:
- ``permissions`` کاتالوگ مرکزی دسترسی‌ها است (کد + بخش + عنوان فارسی + ترتیب).
  بخش‌ها (section) صفحه‌های پنل را روی نقشهٔ منو بازتاب می‌دهند و ستون‌های
  ماتریس در رابط گرافیکی «نقش‌ها و دسترسی‌ها» از همین کاتالوگ ساخته می‌شوند.
- ``role_permissions`` پیوند چند‌به‌چند نقش ↔ دسترسی است؛ اثربخشی کاربر =
  اجتماع دسترسی‌های همهٔ نقش‌های او.
- ``roles.data_scope`` سطح دسترسی **روی داده** است:
    all      → همهٔ داده‌های سامانه
    own      → فقط داده‌های مرتبط با خود کاربر
    assigned → داده‌های تخصیص‌یافته (پرونده/نوبت‌های واگذارشده)
- دسترسی کاربر SYSTEM_ADMIN همیشه کامل است (bypass در deps.require_perm) تا
  مدیر سامانه هرگز خودش را از سامانه قفل نکند.
"""
from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer, String, Table, select
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.menu_registry import LEVEL_RANK, MENU_KEYS
from app.db.base import Base

# مقادیر مجاز data_scope - سطح دسترسی روی داده
DATA_SCOPES = ("all", "own", "assigned")

DATA_SCOPE_TITLES = {
    "all": "همهٔ داده‌ها",
    "own": "فقط داده‌های خودم",
    "assigned": "داده‌های تخصیص‌یافته به من",
}


class Permission(Base):
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(100), primary_key=True)
    section: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(String(200))
    sort: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


role_permissions_table = Table(
    "role_permissions",
    Base.metadata,
    Column(
        "role_code",
        String(50),
        ForeignKey("roles.code", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "permission_code",
        String(100),
        ForeignKey("permissions.code", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class RoleMenuPermission(Base):
    """فاز ۷۱ — ماتریس «نقش × منو/زیرمنو» با سه سطح: دیدن / خواندن / ویرایش.

    نبودِ ردیف = هیچ (منو پنهان + مسیرهای API بخش مسدود).
    نقش SYSTEM_ADMIN ردیفی ندارد — همیشه دسترسی کامل دارد (bypass).
    """

    __tablename__ = "role_menu_permissions"
    __table_args__ = (
        CheckConstraint(
            "level IN ('view','read','edit')",
            name="ck_role_menu_level",
        ),
    )

    role_code: Mapped[str] = mapped_column(
        String(50), ForeignKey("roles.code", ondelete="CASCADE"), primary_key=True
    )
    menu_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    level: Mapped[str] = mapped_column(String(10), nullable=False)


def user_menu_levels(db, user) -> dict[str, str]:
    """سطح مؤثر کاربر روی هر منو = بیشترین سطح میان همهٔ نقش‌های او.

    SYSTEM_ADMIN (یا داشتن دسترسی ``*``) → همهٔ منوها «ویرایش».
    """
    from app.models.rbac import effective_permissions

    perms = effective_permissions(user.roles)
    if "*" in perms or any(r.code == "SYSTEM_ADMIN" for r in user.roles):
        return {key: "edit" for key in MENU_KEYS}
    codes = [r.code for r in user.roles]
    if not codes:
        return {}
    rows = db.scalars(
        select(RoleMenuPermission).where(RoleMenuPermission.role_code.in_(codes))
    ).all()
    merged: dict[str, str] = {}
    for row in rows:
        if row.level not in LEVEL_RANK:
            continue
        cur = merged.get(row.menu_key)
        if cur is None or LEVEL_RANK[row.level] > LEVEL_RANK[cur]:
            merged[row.menu_key] = row.level
    return merged


def effective_permissions(role_rows) -> set[str]:
    """اجتماع کدهای دسترسی از مجموعه نقش‌ها (ورودی: رکوردهای Role)."""
    perms: set[str] = set()
    for role in role_rows:
        if role.code == "SYSTEM_ADMIN":
            return {"*"}
        for p in getattr(role, "permissions", []):
            perms.add(p.code)
    return perms
