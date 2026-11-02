"""فاز ۷۴ — ایزولاسیون دادهٔ سازمانی + روزها و ساعت‌های مشاورهٔ مشاوران

- ``users.organization_id``: هر کاربر می‌تواند به یک سازمان منتسب شود تا
  فقط اطلاعات همان سازمان را ببیند (مدیر سازمان، پذیرش سازمان، مشاور
  سازمان و …). NULL = بدون محدودیت (رفتار قبلی).
- جدول ``counselor_availabilities``: بازه‌های هفتگی مشاورهٔ هر مشاور که
  در کارتابل خودش تعریف می‌کند؛ نوبت‌دهی و رزرو آنلاین فقط در همین
  بازه‌ها پذیرفته می‌شود.
- seed منوی جدید «آزمون‌های برگزارشده سازمانی» (org-exam-results) از
  ``MENU_SEED`` رجیستری (idempotent با ON CONFLICT DO NOTHING).
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0046_org_scope_sched"
down_revision = "0045_rbac_menu_matrix"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- ایمنی: پهن‌کردن version_num تا شناسه‌های بلند آینده هم‌یشه جا شوند
    # (revision «0046_org_scope_counselor_availability» با ۳۶ نویسه در
    #  varchar(32) پیش‌فرض جا نمی‌شد و ارتقا شکست خورد)
    op.execute(
        "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE varchar(128)"
    )

    # --- users.organization_id
    op.add_column(
        "users",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_users_organization_id",
        "users",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_users_organization_id", "users", ["organization_id"])

    # --- counselor_availabilities
    op.create_table(
        "counselor_availabilities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "counselor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("counselors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_counselor_availability_weekday"),
        sa.CheckConstraint("end_time > start_time", name="ck_counselor_availability_range"),
        sa.UniqueConstraint("counselor_id", "weekday", "start_time", name="uq_counselor_availability_slot"),
    )
    op.create_index(
        "ix_counselor_availability_counselor",
        "counselor_availabilities",
        ["counselor_id"],
    )

    # --- seed منوی جدید (از رجیستری — idempotent)
    from app.core.menu_registry import MENU_SEED

    conn = op.get_bind()
    for role, key, level in MENU_SEED:
        if key != "org-exam-results":
            continue
        conn.execute(
            sa.text(
                "INSERT INTO role_menu_permissions (role_code, menu_key, level) "
                "VALUES (:r, :m, :l) ON CONFLICT (role_code, menu_key) DO NOTHING"
            ),
            {"r": role, "m": key, "l": level},
        )


def downgrade() -> None:
    op.execute(
        "DELETE FROM role_menu_permissions WHERE menu_key = 'org-exam-results'"
    )
    op.drop_index("ix_counselor_availability_counselor", table_name="counselor_availabilities")
    op.drop_table("counselor_availabilities")
    op.drop_index("ix_users_organization_id", table_name="users")
    op.drop_constraint("fk_users_organization_id", "users", type_="foreignkey")
    op.drop_column("users", "organization_id")
