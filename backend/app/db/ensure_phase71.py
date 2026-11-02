"""فاز ۷۱ — خودترمیم اسکیمای ماتریس منوها در لحظهٔ راه‌اندازی (دفاع برابر
«کدِ جدید / اسکیمای قدیم»): اگر مایگریشن ۰۰۴۵ به هر دلیل روی بانک اعمال نشده
باشد، همین‌جا idempotent ساخته و seed می‌شود. هیچ‌وقت fatal نیست.

تفاوت با seed مایگریشن: اینجا seed فقط وقتی اجرا می‌شود که جدول «همین الان»
ساخته شده باشد؛ به این ترتیب تنظیم‌های بعدی مدیر در ماتریس گرافیکی هرگز با
ری‌استارت سرور بازنویسی نمی‌شود.
"""
from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger("rosepsy.schema")

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS role_menu_permissions (
        role_code VARCHAR(50) NOT NULL REFERENCES roles(code) ON DELETE CASCADE,
        menu_key VARCHAR(80) NOT NULL,
        level VARCHAR(10) NOT NULL,
        CONSTRAINT pk_role_menu_permissions PRIMARY KEY (role_code, menu_key),
        CONSTRAINT ck_role_menu_level CHECK (level IN ('view','read','edit'))
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_role_menu_menu_key ON role_menu_permissions (menu_key)",
]


def missing_phase71_objects(conn) -> list[str]:
    """فهرست اشیای جاافتادهٔ فاز ۷۱ — خالی یعنی اسکیما سالم است."""
    missing: list[str] = []
    exists = conn.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'role_menu_permissions'"
        )
    ).first()
    if exists is None:
        missing.append("table:role_menu_permissions")
        return missing
    # ایندکس پشتیبان (روی بانک سالم باید موجود باشد)
    idx = conn.execute(
        text(
            "SELECT 1 FROM pg_indexes "
            "WHERE schemaname = 'public' AND indexname = 'ix_role_menu_menu_key'"
        )
    ).first()
    if idx is None:
        missing.append("index:ix_role_menu_menu_key")
    return missing


def ensure_phase71_schema(engine: Engine) -> list[str]:
    """ساخت/ترمیم idempotent؛ فهرست موارد ترمیم‌شده را برمی‌گرداند ([] = سالم)."""
    with engine.connect() as conn:
        missing = missing_phase71_objects(conn)
        if not missing:
            return []
        repaired: list[str] = []
        table_was_missing = any(m.startswith("table:") for m in missing)
        for ddl in _DDL:
            conn.execute(text(ddl))
        conn.commit()
        if table_was_missing:
            from app.core.menu_registry import MENU_SEED

            for role_code, menu_key, level in MENU_SEED:
                conn.execute(
                    text(
                        "INSERT INTO role_menu_permissions (role_code, menu_key, level) "
                        "VALUES (:r, :m, :l) ON CONFLICT (role_code, menu_key) DO NOTHING"
                    ),
                    {"r": role_code, "m": menu_key, "l": level},
                )
            conn.commit()
            repaired.append("role_menu_permissions+seed")
        else:
            repaired.append("ix_role_menu_menu_key")
        logger.warning("phase71 self-heal repaired: %s", ", ".join(repaired))
        return repaired
