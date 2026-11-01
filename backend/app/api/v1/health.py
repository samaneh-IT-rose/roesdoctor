from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import engine

router = APIRouter()


def _phase70_schema_ok() -> bool | None:
    """وضعیت اشیای فاز ۷۰ روی بانک: True/False؛ None = بانک/وارسی در دسترس نیست.

    فاز ۷۰ ب — برای وارسی از راه دور بدون احراز هویت: deploy و پایش می‌توانند
    با همین پرچم بفهمند اسکیمای فاز ۷۰ کامل است یا نه.
    """
    try:
        if engine.dialect.name != "postgresql":
            return None
        from app.db.ensure_phase70 import missing_phase70_objects

        with engine.connect() as conn:
            return not missing_phase70_objects(conn)
    except Exception:  # noqa: BLE001 — health هرگز نباید خطا بدهد
        return None


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "phase70_schema": _phase70_schema_ok()}


@router.get("/health/db")
def health_db() -> dict:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}
