"""فاز ۷۰ - پروندهٔ مشاورهٔ کاربر + تاریخچهٔ آزمون‌ها و مشاوره‌ها.

- user_counseling_files: یک پروندهٔ مشاوره برای هر کاربر (خودکار) — شمارهٔ
  پرونده یکتا (UF-…)، یادداشت پذیرش و زمان آخرین فعالیت.
- psych_attempts.viewed_at: زمان دیده‌شدن نتیجه توسط خود کاربر (لیست
  «نتایج دیده‌شده»).
- psych_attempts.case_id: اتصال آزمون به پروندهٔ بالینی — «ایجاد پرونده
  برای کسی که آزمون داده» از پنل کارکنان.

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


def upgrade() -> None:
    # --- پروندهٔ مشاورهٔ کاربر ---
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
    op.create_index("ix_ucf_updated", "user_counseling_files", ["updated_at"])

    # --- آزمون‌ها: دیده‌شدن نتیجه + اتصال به پروندهٔ بالینی ---
    op.add_column(
        "psych_attempts",
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "psych_attempts",
        sa.Column("case_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_psych_attempts_case", "psych_attempts", "cases",
        ["case_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_psych_attempts_case", "psych_attempts", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_psych_attempts_case", table_name="psych_attempts")
    op.drop_constraint("fk_psych_attempts_case", "psych_attempts", type_="foreignkey")
    op.drop_column("psych_attempts", "case_id")
    op.drop_column("psych_attempts", "viewed_at")
    op.drop_index("ix_ucf_updated", table_name="user_counseling_files")
    op.drop_table("user_counseling_files")
