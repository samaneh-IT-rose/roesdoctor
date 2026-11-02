r"""وارسی و ترمیم خودکار اسکیمای بانک — فاز ۷۰ / نسخهٔ deploy ۱.۰.۳۰.

مشکل میدانی: سرور با کد ۰.۵۴.۰ بالا آمده بود ولی اسکیمای فاز ۷۰ (مایگریشن
۰۰۴۴) روی بانک اعمال نشده بود؛ نتیجه: صفحه‌های «آزمون‌های برگزار شده» و
«پرونده‌های مشاوره» در پنل با «خطای نامشخص رخ داد» (500 بدون detail) مواجه
می‌شدند. این اسکریپت در deploy بلافاصله پس از alembic اجرا می‌شود و:

۱) وضعیت فعلی را چاپ می‌کند (alembic_version + اشیای فاز ۷۰)؛
۲) اگر چیزی غایب باشد، با SQL idempotent (IF NOT EXISTS) ترمیم می‌کند؛
۳) دوباره وارسی می‌کند — اگر همه‌چیز سبز شد کد خروج ۰، وگرنه ۱
   (deploy دقیقاً همین‌جا با پیام روشن متوقف می‌شود، نه با ۵۰۰ بی‌صدا).

اجرا از deploy:  & $VenvPy C:\rosepsy\app\backend\scripts\verify_schema_phase70.py
(متغیر محیطی DATABASE_URL را می‌خواند؛ اگر نبود، backend\.env را می‌خواند.)
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

REPAIR_SQL = [
    # ۱) جدول پروندهٔ مشاورهٔ کاربر (فاز ۷۰)
    """
    CREATE TABLE IF NOT EXISTS user_counseling_files (
        id UUID PRIMARY KEY,
        user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
        file_code VARCHAR(30) NOT NULL UNIQUE,
        staff_note VARCHAR(2000),
        created_at TIMESTAMPTZ DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        last_activity_at TIMESTAMPTZ
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_ucf_updated ON user_counseling_files (updated_at)",
    # ۲) ستون‌های فاز ۷۰ روی psych_attempts
    ("COLUMN", "psych_attempts", "viewed_at", "TIMESTAMPTZ"),
    ("COLUMN", "psych_attempts", "case_id", "UUID"),
    # ۳) کلید خارجی + ایندکس اتصال آزمون به پروندهٔ بالینی
    """
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
    """,
    "CREATE INDEX IF NOT EXISTS ix_psych_attempts_case ON psych_attempts (case_id)",
]

OK = "\u2713"
BAD = "\u2717"


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if url:
        return url
    env_file = Path(__file__).resolve().parents[1] / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            m = re.match(r"^\s*DATABASE_URL\s*=\s*(.+?)\s*$", line)
            if m:
                return m.group(1).strip().strip('"').strip("'")
    return "postgresql+psycopg://rosepsy:change_me@localhost:5432/rosepsy"


def _connect():
    url = _database_url()
    if url.startswith("postgresql+psycopg://"):
        url = url.replace("postgresql+psycopg://", "postgresql://", 1)
    import psycopg

    return psycopg.connect(url)


def _probe(cur) -> dict:
    state: dict = {}
    cur.execute("SELECT version_num FROM alembic_version")
    row = cur.fetchone()
    state["alembic"] = row[0] if row else "(خالی)"
    cur.execute("SELECT to_regclass('user_counseling_files') IS NOT NULL")
    state["table_ucf"] = bool(cur.fetchone()[0])
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'psych_attempts'"
    )
    cols = {r[0] for r in cur.fetchall()}
    state["col_viewed_at"] = "viewed_at" in cols
    state["col_case_id"] = "case_id" in cols
    cur.execute(
        "SELECT 1 FROM pg_constraint WHERE conname = 'fk_psych_attempts_case' "
        "AND conrelid = 'psych_attempts'::regclass"
    )
    state["fk_case"] = cur.fetchone() is not None
    cur.execute(
        "SELECT 1 FROM pg_indexes WHERE indexname = 'ix_psych_attempts_case'"
    )
    state["ix_case"] = cur.fetchone() is not None
    cur.execute("SELECT to_regclass('cases') IS NOT NULL")
    state["table_cases"] = bool(cur.fetchone()[0])
    cur.execute("SELECT to_regclass('users') IS NOT NULL")
    state["table_users"] = bool(cur.fetchone()[0])
    return state


def _missing(state: dict) -> list[str]:
    out = []
    if not state["table_ucf"]:
        out.append("جدول user_counseling_files")
    if not state["col_viewed_at"]:
        out.append("ستون psych_attempts.viewed_at")
    if not state["col_case_id"]:
        out.append("ستون psych_attempts.case_id")
    if not state["fk_case"]:
        out.append("کلید خارجی fk_psych_attempts_case")
    if not state["ix_case"]:
        out.append("ایندکس ix_psych_attempts_case")
    return out


def main() -> int:
    print("=== وارسی اسکیمای بانک (فاز ۷۰) ===")
    try:
        conn = _connect()
    except Exception as exc:  # noqa: BLE001
        print(f"[{BAD}] اتصال به بانک ناموفق: {exc}")
        return 1
    try:
        with conn.cursor() as cur:
            state = _probe(cur)
            print(
                f"  alembic_version: {state['alembic']}  |  "
                f"جدول پرونده: {OK if state['table_ucf'] else BAD}  |  "
                f"viewed_at: {OK if state['col_viewed_at'] else BAD}  |  "
                f"case_id: {OK if state['col_case_id'] else BAD}  |  "
                f"FK پرونده: {OK if state['fk_case'] else BAD}"
            )
            if state["alembic"] != "0044_user_counseling_file":
                # اطلاع‌رسانی خنثی — ملاکِ واقعی، وارسی اشیای پایین است نه شمارهٔ سر
                print(
                    f"  [i] alembic_version اکنون «{state['alembic']}» است "
                    "(جدیدتر از پایهٔ فاز ۷۰) — ملاک، وارسی اشیای زیر است."
                )
            miss = _missing(state)
            if not miss:
                print(f"[{OK}] اسکیمای فاز ۷۰ کامل است — نیازی به ترمیم نیست.")
                return 0
            print(f"  [{BAD}] اشیای غایب: {', '.join(miss)} — ترمیم خودکار...")
            if not (state["table_cases"] and state["table_users"]):
                print(
                    f"  [{BAD}] جداول پایه cases/users غایب‌اند — ترمیم ممکن نیست؛ "
                    "با پشتیبانی تماس بگیرید."
                )
                return 1
            for stmt in REPAIR_SQL:
                if isinstance(stmt, tuple):
                    _tag, table, col, ctype = stmt
                    cur.execute(
                        "SELECT 1 FROM information_schema.columns "
                        "WHERE table_name = %s AND column_name = %s",
                        (table, col),
                    )
                    if cur.fetchone() is None:
                        cur.execute(
                            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {ctype}"
                        )
                        print(f"    + ستون {table}.{col} اضافه شد")
                    continue
                cur.execute(stmt)
            conn.commit()
            state2 = _probe(cur)
            still = _missing(state2)
            if still:
                print(f"[{BAD}] پس از ترمیم هنوز غایب است: {', '.join(still)}")
                return 1
            print(f"[{OK}] ترمیم انجام شد و اسکیمای فاز ۷۰ کامل است.")
            return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[{BAD}] خطا در وارسی/ترمیم اسکیما: {exc}")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
