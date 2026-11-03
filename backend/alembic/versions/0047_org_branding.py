"""فاز ۷۵ — برندینگ سازمانی آزمون‌ها + عنوان نمایشی آزمون در برنامهٔ سازمانی

- ``organizations.brand_name``: نام برند/نمایشی سازمان (مثلاً «پتروپارس»)
- ``organizations.brand_logo_path``: مسیر لوگو در uploads/org_logos (سرو عمومی)
- ``organizations.entry_title``: عنوان دلخواه صفحه ورودی آزمون کارکنان
- ``organizations.entry_note``: پیام/توضیح دلخواه صفحه ورودی آزمون
- ``org_program_tests.display_title``: عنوان نمایشی آزمون برای شرکت‌کنندگان
  همان برنامه (مثلاً به‌جای «پرسشنامه سلامت عمومی (GHQ-28)»، «ارزیابی
  سلامت کارکنان») — NULL = عنوان اصلی آزمون.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0047_org_branding"
down_revision = "0046_org_scope_sched"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("brand_name", sa.String(120), nullable=True))
    op.add_column("organizations", sa.Column("brand_logo_path", sa.String(300), nullable=True))
    op.add_column("organizations", sa.Column("entry_title", sa.String(200), nullable=True))
    op.add_column("organizations", sa.Column("entry_note", sa.Text(), nullable=True))
    op.add_column("org_program_tests", sa.Column("display_title", sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column("org_program_tests", "display_title")
    op.drop_column("organizations", "entry_note")
    op.drop_column("organizations", "entry_title")
    op.drop_column("organizations", "brand_logo_path")
    op.drop_column("organizations", "brand_name")
