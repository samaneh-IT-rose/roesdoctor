"""فاز ۶۹ - پرداخت آنلاین رزرو (زرین‌پال) + نظرسنجی و امتیازدهی مشاوران.

- consultation_requests: payment_status/paid_at/review_token
  (رزرو آنلاین با پرداخت درگاه، توکن دعوت به ثبت نظر پس از تأیید پرداخت).
- orders: consultation_request_id (اتصال یکتای سفارش به رزرو عمومی).
- counselor_reviews: جدول نظرات کاربران دربارهٔ مشاوران (امتیاز ۱ تا ۵).

Revision ID: 0043_booking_payment_reviews
Revises: 0042_counselor_clinic
Create Date: 2026-11-01
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0043_booking_payment_reviews"
down_revision = "0042_counselor_clinic"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- consultation_requests: وضعیت پرداخت آنلاین + توکن نظر ---
    op.add_column(
        "consultation_requests",
        sa.Column("payment_status", sa.String(length=20), nullable=False,
                  server_default="not_required"),
    )
    op.add_column(
        "consultation_requests",
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "consultation_requests",
        sa.Column("review_token", sa.String(length=64), nullable=True),
    )
    op.create_check_constraint(
        "ck_consult_payment_status", "consultation_requests",
        "payment_status IN ('not_required','pending','paid','failed')",
    )
    op.create_index(
        "ix_consult_payment_status", "consultation_requests", ["payment_status"]
    )
    op.create_unique_constraint(
        "uq_consult_review_token", "consultation_requests", ["review_token"]
    )

    # --- orders: اتصال یکتا به رزرو عمومی ---
    op.add_column(
        "orders",
        sa.Column("consultation_request_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_orders_consultation_request", "orders", "consultation_requests",
        ["consultation_request_id"], ["id"], ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_orders_consultation_request", "orders", ["consultation_request_id"]
    )
    op.create_index(
        "ix_orders_consultation_request", "orders", ["consultation_request_id"]
    )

    # --- counselor_reviews: نظرات و امتیاز کاربران ---
    op.create_table(
        "counselor_reviews",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "counselor_id", UUID(as_uuid=True),
            sa.ForeignKey("counselors.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "author_user_id", UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "consultation_request_id", UUID(as_uuid=True),
            sa.ForeignKey("consultation_requests.id", ondelete="SET NULL"),
            nullable=True, unique=True,
        ),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.String(length=1000), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_counselor_reviews_rating"),
    )
    op.create_index(
        "ix_counselor_reviews_counselor_published", "counselor_reviews",
        ["counselor_id", "is_published"],
    )
    op.create_index(
        "ix_counselor_reviews_author", "counselor_reviews", ["author_user_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_counselor_reviews_author", table_name="counselor_reviews")
    op.drop_index("ix_counselor_reviews_counselor_published", table_name="counselor_reviews")
    op.drop_table("counselor_reviews")
    op.drop_index("ix_orders_consultation_request", table_name="orders")
    op.drop_constraint("uq_orders_consultation_request", "orders", type_="unique")
    op.drop_constraint("fk_orders_consultation_request", "orders", type_="foreignkey")
    op.drop_column("orders", "consultation_request_id")
    op.drop_constraint("uq_consult_review_token", "consultation_requests", type_="unique")
    op.drop_index("ix_consult_payment_status", table_name="consultation_requests")
    op.drop_constraint("ck_consult_payment_status", "consultation_requests", type_="check")
    op.drop_column("consultation_requests", "review_token")
    op.drop_column("consultation_requests", "paid_at")
    op.drop_column("consultation_requests", "payment_status")
