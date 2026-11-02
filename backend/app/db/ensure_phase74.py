"""فاز ۷۴ — خودترمیم اسکیمای ایزولاسیون سازمانی + روزهای مشاوره در لحظهٔ
راه‌اندازی (دفاع برابر «کدِ جدید / اسکیمای قدیم»): اگر مایگریشن ۰۰۴۶ به هر
دلیل روی بانک اعمال نشده باشد، همین‌جا idempotent ساخته می‌شود. هیچ‌وقت
fatal نیست.

تفاوت با seed مایگریشن: seed منوی جدید فقط وقتی اجرا می‌شود که ستون/جدول
«همین الان» ساخته شده باشد تا تنظیم‌های بعدی مدیر در ماتریس هرگز با
ری‌استارت بازنویسی نشود (همان قرارداد ensure_phase71).
"""
from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger("rosepsy.schema")

_DDL = [
    # users.organization_id (ایزولاسیون دادهٔ سازمانی)
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS organization_id UUID NULL",
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'fk_users_organization_id'
        ) THEN
            ALTER TABLE users ADD CONSTRAINT fk_users_organization_id
                FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE SET NULL;
        END IF;
    END $$;
    """,
    "CREATE INDEX IF NOT EXISTS ix_users_organization_id ON users (organization_id)",
    # روزها و ساعت‌های مشاورهٔ مشاوران
    """
    CREATE TABLE IF NOT EXISTS counselor_availabilities (
        id UUID PRIMARY KEY,
        counselor_id UUID NOT NULL REFERENCES counselors(id) ON DELETE CASCADE,
        weekday INTEGER NOT NULL,
        start_time TIME NOT NULL,
        end_time TIME NOT NULL,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT ck_counselor_availability_weekday CHECK (weekday BETWEEN 0 AND 6),
        CONSTRAINT ck_counselor_availability_range CHECK (end_time > start_time),
        CONSTRAINT uq_counselor_availability_slot UNIQUE (counselor_id, weekday, start_time)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_counselor_availability_counselor
        ON counselor_availabilities (counselor_id)
    """,
]


def missing_phase74_objects(conn) -> list[str]:
    """فهرست اشیای جاافتادهٔ فاز ۷۴ — خالی یعنی اسکیما سالم است."""
    missing: list[str] = []
    col = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'users' "
            "AND column_name = 'organization_id'"
        )
    ).first()
    if col is None:
        missing.append("column:users.organization_id")
    tbl = conn.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'counselor_availabilities'"
        )
    ).first()
    if tbl is None:
        missing.append("table:counselor_availabilities")
    return missing


def ensure_phase74_schema(engine: Engine) -> list[str]:
    """ساخت/ترمیم idempotent؛ فهرست موارد ترمیم‌شده را برمی‌گرداند ([] = سالم)."""
    with engine.connect() as conn:
        missing = missing_phase74_objects(conn)
        if not missing:
            return []
        repaired: list[str] = []
        for ddl in _DDL:
            conn.execute(text(ddl))
        conn.commit()
        repaired.append("+".join(missing))
        # seed منوی جدید «آزمون‌های برگزارشده سازمانی» — فقط در لحظهٔ ترمیم
        from app.core.menu_registry import MENU_SEED

        for role_code, menu_key, level in MENU_SEED:
            if menu_key != "org-exam-results":
                continue
            conn.execute(
                text(
                    "INSERT INTO role_menu_permissions (role_code, menu_key, level) "
                    "VALUES (:r, :m, :l) ON CONFLICT (role_code, menu_key) DO NOTHING"
                ),
                {"r": role_code, "m": menu_key, "l": level},
            )
        conn.commit()
        repaired.append("org-exam-results+seed")
        logger.warning("phase74 self-heal repaired: %s", ", ".join(repaired))
        return repaired
