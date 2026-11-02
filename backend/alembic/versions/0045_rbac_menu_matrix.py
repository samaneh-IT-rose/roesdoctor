"""فاز ۷۱ — ماتریس دسترسی منوها و زیرمنوها (سه سطح: دیدن / خواندن / ویرایش)

- جدول ``role_menu_permissions``: (role_code, menu_key) → level
  level ∈ ('view','read','edit') — نبودِ ردیف یعنی هیچ (منو پنهان + API مسدود).
- seed نگاشت پیش‌فرض نقش‌های سیستمی از ``app.core.menu_registry.MENU_SEED``
  (idempotent با ON CONFLICT DO NOTHING) — وضعیت فعلی منوهای هر نقش را دقیقاً
  بازتولید می‌کند تا پس از استقرار هیچ‌کس منویی را از دست ندهد؛ از این نقطه
  مدیر از صفحهٔ «نقش‌ها و دسترسی‌ها» هر سلول ماتریس را می‌تواند تغییر دهد.
- نقش SYSTEM_ADMIN عمداً ردیفی ندارد — همیشه دسترسی کامل دارد (bypass).
"""

from alembic import op
import sqlalchemy as sa

revision = "0045_rbac_menu_matrix"
down_revision = "0044_user_counseling_file"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.core.menu_registry import MENU_SEED

    op.create_table(
        "role_menu_permissions",
        sa.Column("role_code", sa.String(50),
                  sa.ForeignKey("roles.code", ondelete="CASCADE"), primary_key=True),
        sa.Column("menu_key", sa.String(80), primary_key=True),
        sa.Column("level", sa.String(10), nullable=False),
        sa.CheckConstraint("level IN ('view','read','edit')", name="ck_role_menu_level"),
    )
    op.create_index(
        "ix_role_menu_menu_key", "role_menu_permissions", ["menu_key"]
    )

    conn = op.get_bind()
    for role_code, menu_key, level in MENU_SEED:
        conn.execute(
            sa.text(
                "INSERT INTO role_menu_permissions (role_code, menu_key, level) "
                "VALUES (:r, :m, :l) ON CONFLICT (role_code, menu_key) DO NOTHING"
            ),
            {"r": role_code, "m": menu_key, "l": level},
        )


def downgrade() -> None:
    op.drop_index("ix_role_menu_menu_key", table_name="role_menu_permissions")
    op.drop_table("role_menu_permissions")
