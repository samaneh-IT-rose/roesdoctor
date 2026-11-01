"""فاز ۷۰ ب — دفاع نهایی برابر «کدِ جدید / اسکیمای قدیم» + خطای ۵۰۰ قابل‌ردیابی.

عارضهٔ میدانی: سرور با کد ۰.۵۴.۱ بالا آمده بود ولی صفحات فاز ۷۰ «خطای نامشخص
رخ داد» می‌دادند؛ چون هر استثنای مدیریت‌نشده‌ای پاسخ ۵۰۰ متنیِ بی‌نام می‌شد و
پنل نمی‌توانست علت را نشان دهد. این آزمون‌ها سه لایهٔ تازه را قفل می‌کنند:

۱) ensure_phase70_schema — اسکیمای سالم دست‌نخورده می‌ماند (idempotent)؛
۲) /health پرچم phase70_schema را گزارش می‌کند (وارسی از راه دور)؛
۳) هندلر سراسری Exception → ۵۰۰ با نام کلاس خطا + کد پیگیری (نه متن خام).
"""
from fastapi.testclient import TestClient

from app.db.ensure_phase70 import ensure_phase70_schema, missing_phase70_objects
from app.db.session import engine
from app.main import app


def test_phase70_schema_healthy_and_ensure_idempotent():
    """اسکیمای فاز ۷۰ روی بانک تست کامل است و ensure دوباره چیزی نمی‌سازد."""
    with engine.connect() as conn:
        assert missing_phase70_objects(conn) == []
    # اجرای دوباره روی اسکیمای سالم → بدون هیچ تغییر و بدون خطا
    assert ensure_phase70_schema(engine) == []


def test_health_reports_phase70_schema(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    # روی PostgreSQL تست باید True باشد (None فقط وقتی بانک/دیالکت در دسترس نیست)
    assert body.get("phase70_schema") is True


def test_unhandled_exception_returns_trackable_500():
    """هر خطای مدیریت‌نشده → JSON با نام کلاس + کد پیگیری، نه ۵۰۰ متنی خام."""

    def _boom():
        raise RuntimeError("boom-70b")

    route_path = "/api/v1/_test_boom_70b"
    app.add_api_route(route_path, _boom, methods=["GET"], include_in_schema=False)
    try:
        # raise_server_exceptions=False → پاسخِ هندلر سراسری را می‌بینیم
        with TestClient(app, raise_server_exceptions=False) as c:
            r = c.get(route_path)
        assert r.status_code == 500
        detail = r.json()["detail"]
        assert "RuntimeError" in detail
        assert "کد پیگیری" in detail
    finally:
        # پاک‌سازی: مسیر موقت آزمون از اپ اصلی حذف شود
        app.router.routes[:] = [
            rt
            for rt in app.router.routes
            if getattr(rt, "path", None) != route_path
        ]
