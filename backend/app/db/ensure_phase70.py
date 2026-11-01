"""فاز ۷۰ ب — ترمیم خودکار اسکیمای فاز ۷۰ داخل خودِ API (دفاع نهایی).

چرا این ماژول وجود دارد؟ تجربهٔ میدانی فاز ۷۰ الف: سرور با کدِ ۰.۵۴.۰ بالا
آمده بود ولی مایگریشن ۰۰۴۴ روی بانک اعمال نشده بود (نسخهٔ قدیمی اسکریپت deploy
در حافظهٔ PowerShell باقی مانده بود و گام‌های تازهٔ فایل تازه اجرا نشدند)؛
نتیجه: ۵۰۰ بی‌صدای «خطای نامشخص رخ داد» در صفحات فاز ۷۰.

این ماژول همان ترمیم idempotent اسکریپت deploy (backend/scripts/
verify_schema_phase70.py) را داخل خود API اجرا می‌کند — در «راه‌اندازی» سرویس.
با این کار دیگر هیچ وضعیتی (alembic عقب‌مانده، deploy نسخهٔ قدیمی، ری‌استارت
دستی سرویس) نمی‌تواند API را با اسکیمای ناقص فاز ۷۰ بالا ببرد: کد و اسکیما
همیشه هم‌زمان در یک فرایند بالا می‌آیند.

اصول:
- فقط روی PostgreSQL اجرا می‌شود؛ سایر دیالکت‌ها بی‌صدا رد می‌شوند؛
- هر گام «اگر نبود بساز» است (IF NOT EXISTS) — اجرای تکراری کاملاً بی‌اثر؛
- هر خطا فقط لاگ می‌شود («rosepsy.schema») — راه‌اندازی هرگز به‌خاطر آن
  نمی‌میرد (مثلاً بانک هنوز بالا نیامده؛ دفعهٔ بعدی که اتصال برقرار شود،
  health وضعیت را نشان می‌دهد و deploy هم verify خودش را دارد).
"""
from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

log = logging.getLogger("rosepsy.schema")

_CREATE_UCF = text("""
    CREATE TABLE IF NOT EXISTS user_counseling_files (
        id UUID PRIMARY KEY,
        user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
        file_code VARCHAR(30) NOT NULL UNIQUE,
        staff_note VARCHAR(2000),
        created_at TIMESTAMPTZ DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        last_activity_at TIMESTAMPTZ
    )
""")

_FK_CASE = text("""
    DO $$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'fk_psych_attempts_case'
              AND conrelid = 'psych_attempts'::regclass
        ) THEN
            ALTER TABLE psych_attempts
              ADD CONSTRAINT fk_psych_attempts_case
              FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE SET NULL;
        END IF;
    END $$;
""")


def missing_phase70_objects(bind: Connection) -> list[str]:
    """فهرست اشیای فاز ۷۰ که روی این بانک غایب‌اند (خالی = همه سبز)."""
    miss: list[str] = []
    ucf = bind.execute(
        text("SELECT to_regclass('user_counseling_files') IS NOT NULL")
    ).scalar()
    if not ucf:
        miss.append("جدول user_counseling_files")
    cols = {
        r[0]
        for r in bind.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'psych_attempts'"
            )
        ).fetchall()
    }
    if "viewed_at" not in cols:
        miss.append("ستون psych_attempts.viewed_at")
    if "case_id" not in cols:
        miss.append("ستون psych_attempts.case_id")
    fk = bind.execute(
        text(
            "SELECT 1 FROM pg_constraint WHERE conname = 'fk_psych_attempts_case' "
            "AND conrelid = 'psych_attempts'::regclass"
        )
    ).first()
    if fk is None:
        miss.append("کلید خارجی fk_psych_attempts_case")
    ix = bind.execute(
        text("SELECT 1 FROM pg_indexes WHERE indexname = 'ix_psych_attempts_case'")
    ).first()
    if ix is None:
        miss.append("ایندکس ix_psych_attempts_case")
    return miss


def ensure_phase70_schema(engine: Engine) -> list[str]:
    """اشیای غایب فاز ۷۰ را می‌سازد و فهرست آن‌ها را برمی‌گرداند.

    - اسکیمای سالم → خروجی [] بدون هیچ DDL (کم‌هزینه، فقط وارسی)؛
    - هر خطا فقط لاگ می‌شود و [] برمی‌گردد — هرگز exception نمی‌دهد.
    """
    try:
        if engine.dialect.name != "postgresql":
            return []
        with engine.begin() as conn:
            miss = missing_phase70_objects(conn)
            if not miss:
                return []
            log.warning(
                "phase70 schema is missing: %s — repairing at startup",
                ", ".join(miss),
            )
            ucf = conn.execute(
                text("SELECT to_regclass('user_counseling_files') IS NOT NULL")
            ).scalar()
            if not ucf:
                conn.execute(_CREATE_UCF)
            conn.execute(text(
                "ALTER TABLE psych_attempts "
                "ADD COLUMN IF NOT EXISTS viewed_at TIMESTAMPTZ"
            ))
            conn.execute(text(
                "ALTER TABLE psych_attempts "
                "ADD COLUMN IF NOT EXISTS case_id UUID"
            ))
            conn.execute(_FK_CASE)
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_psych_attempts_case "
                "ON psych_attempts (case_id)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_ucf_updated "
                "ON user_counseling_files (updated_at)"
            ))
            still = missing_phase70_objects(conn)
            if still:
                log.error(
                    "phase70 self-heal incomplete, still missing: %s",
                    ", ".join(still),
                )
                return []
            log.warning("phase70 self-heal repaired: %s", ", ".join(miss))
            return miss
    except Exception:  # noqa: BLE001 — راه‌اندازی نباید به‌خاطر ترمیم بمیرد
        log.exception("phase70 startup self-heal failed (non-fatal)")
        return []
