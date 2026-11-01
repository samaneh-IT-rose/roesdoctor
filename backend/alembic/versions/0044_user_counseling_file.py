"""فاز ۷۰ - پروندهٔ مشاورهٔ کاربر + تاریخچهٔ آزمون‌ها و مشاوره‌ها.

- user_counseling_files: یک پروندهٔ مشاوره برای هر کاربر (خودکار) — شمارهٔ
  پرونده یکتا (UF-…)، یادداشت پذیرش و زمان آخرین فعالیت.
- psych_attempts.viewed_at: زمان دیده‌شدن نتیجه توسط خود کاربر (لیست
  «نتایج دیده‌شده»).
- psych_attempts.case_id: اتصال آزمون به پروندهٔ بالینی — «ایجاد پرونده
  برای کسی که آزمون داده» از پنل کارکنان.

۱.۰.۳۰ / فاز ۷۰ الف — مایگریشن idempotent شد: روی سرور واقعی احتمال دارد
اجرای قبلی نیمه‌کاره مانده باشد (قطع برق/بستن پنجره/قفل طولانی) یا
alembic_version جلوتر از اسکیمای واقعی باشد؛ در این حالت اجرای دوباره با
«جدول تکراری/ستون تکراری» خطا می‌داد و کل deploy متوقف می‌شد — عارضهٔ
میدانی: API با کدِ جدید بالا می‌آید ولی کوئری‌های فاز ۷۰ روی اسکیمای قدیمی
500 می‌دهند. اکنون هر گام پیش از اجرا وجود شیء را بررسی می‌کند و در صورت
وجود، بی‌صدا رد می‌شود (هم‌راستا با verify_schema_phase70.py در deploy).

Revision ID: 0044_user_counseling_file
Revises: 0043_booking_payment_reviews
Create Date: 2026-11-01
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0044_user_counseling_file"
down_revision = "0043_booking_payment_reviews"
branch_labels = None
depends_on = None


def _has_table(bind, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def _columns(bind, table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(bind).get_columns(table)}


def _has_index(bind, table: str, name: str) -> bool:
    return any(i["name"] == name for i in sa.inspect(bind).get_indexes(table))


def _has_fk(bind, table: str, name: str) -> bool:
    return any(fk.get("name") == name for fk in sa.inspect(bind).get_foreign_keys(table))


def upgrade() -> None:
    bind = op.get_bind()

    # --- پروندهٔ مشاورهٔ کاربر ---
    if not _has_table(bind, "user_counseling_files"):
        op.create_table(
            "user_counseling_files",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "user_id", UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True,
            ),
            sa.Column("file_code", sa.String(length=30), nullable=False, unique=True),
            sa.Column("staff_note", sa.String(length=2000), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True),
                server_default=sa.func.now(), nullable=False,
            ),
            sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not _has_index(bind, "user_counseling_files", "ix_ucf_updated"):
        op.create_index("ix_ucf_updated", "user_counseling_files", ["updated_at"])

    # --- آزمون‌ها: دیده‌شدن نتیجه + اتصال به پروندهٔ بالینی ---
    cols = _columns(bind, "psych_attempts")
    if "viewed_at" not in cols:
        op.add_column(
            "psych_attempts",
            sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "case_id" not in cols:
        op.add_column(
            "psych_attempts",
            sa.Column("case_id", UUID(as_uuid=True), nullable=True),
        )
    if not _has_fk(bind, "psych_attempts", "fk_psych_attempts_case"):
        op.create_foreign_key(
            "fk_psych_attempts_case", "psych_attempts", "cases",
            ["case_id"], ["id"], ondelete="SET NULL",
        )
    if not _has_index(bind, "psych_attempts", "ix_psych_attempts_case"):
        op.create_index("ix_psych_attempts_case", "psych_attempts", ["case_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if _has_index(bind, "psych_attempts", "ix_psych_attempts_case"):
        op.drop_index("ix_psych_attempts_case", table_name="psych_attempts")
    if _has_fk(bind, "psych_attempts", "fk_psych_attempts_case"):
        op.drop_constraint("fk_psych_attempts_case", "psych_attempts", type_="foreignkey")
    if "case_id" in _columns(bind, "psych_attempts"):
        op.drop_column("psych_attempts", "case_id")
    if "viewed_at" in _columns(bind, "psych_attempts"):
        op.drop_column("psych_attempts", "viewed_at")
    if _has_index(bind, "user_counseling_files", "ix_ucf_updated"):
        op.drop_index("ix_ucf_updated", table_name="user_counseling_files")
    if _has_table(bind, "user_counseling_files"):
        op.drop_table("user_counseling_files")
