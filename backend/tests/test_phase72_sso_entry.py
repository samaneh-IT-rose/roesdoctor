"""فاز ۷۲ — ورود یکپارچه (SSO) رز هاب: رفع باگ «کاربر SSO وارد برنامه نمی‌شود».

دو علت میدانی (هر دو با پروب زندهٔ سرور ۱۴۰۴/۰۸/۱۱ اثبات شد) و ترمیم هرکدام:

1) مقصد دکمهٔ SSO مستقیم ``/api/sso/launch?clientId=...`` بود؛ رز هاب برای
   کاربرِ واردنشده ``307 → http://localhost:8082/login`` می‌داد که در مرورگر
   کاربر باز نمی‌شود و جریان می‌شکست → مقصد جدید صفحهٔ ورود خودِ درگاه روی
   نشانی عمومی است (``/login?next=%2Fapi%2Fsso%2Flaunch...``) تا نشانی در
   نوار آدرس روی 130.185.73.157:8082 بماند.

2) اسپای پنل پس از فاز ۷۱ وقتی توکن دسترسی (حافظه) و پرچم نشست
   (localStorage) ندارد /auth/me را صدا نمی‌زند؛ کاربر SSO فقط کوکی refresh
   (HttpOnly) دارد → در صفحهٔ ورود گیر می‌کرد → پراپ بی‌صدای
   ``GET /auth/session-probe`` (همیشه 200) + بازیابی خودکار توکن با
   ``POST /auth/refresh`` → ورود کامل بدون صفحهٔ login؛ و کنسول برای
   بازدیدکنندهٔ ناشناس هم بی‌خطا می‌ماند.
"""
import jwt

from app.core.config import get_settings
from app.models.user import User
from app.db.session import SessionLocal
from sqlalchemy import select

settings = get_settings()
EMAIL = "7780012222@rose.ir"
NID = "7780012222"


def _hub_token(**overrides) -> str:
    """توکن SSO با همان قواعد رز هاب (HS256 با clientSecret رز سای)."""
    claims = {
        "iss": "rose-hub",
        "aud": settings.rose_hub_client_id,
        "sub": "test-hub-user-72",
        "email": EMAIL,
        "name": "آزمون ورود یکپارچه فاز ۷۲",
        "role": "THERAPIST",
        "nationalId": NID,
        "mobile": "09141110000",
        "scope": "sso-launch",
    }
    claims.update(overrides)
    return jwt.encode(claims, settings.rose_hub_client_secret, algorithm="HS256")


def _fresh_session(client):
    """کوکی‌های مانده از آزمون قبلی (client session-scoped است) پاک می‌شود
    تا هر آزمون SSO از وضعیت خالص شروع کند — مثل مرورگر تازه."""
    client.cookies.clear()


def test_session_probe_anonymous_is_200_not_401(client):
    """پراپ نشست برای ناشناس همیشه 200 است — بدون هیچ خطایی در کنسول مرورگر."""
    _fresh_session(client)  # client session-scoped است؛ کوکی آزمون‌های قبلی نباید بنشیند
    r = client.get("/api/v1/auth/session-probe")
    assert r.status_code == 200, r.text
    assert r.json() == {"authenticated": False}

    # همان endpoint روی v2 با پاکت استاندارد و باز هم 200
    r2 = client.get("/api/v2/auth/session-probe")
    assert r2.status_code == 200
    assert r2.json()["data"]["authenticated"] is False


def test_rose_hub_launch_url_targets_portal_login_not_localhost():
    """مقصد SSO باید صفحهٔ ورود درگاه روی نشانی عمومی باشد — نه localhost."""
    url = settings.rose_hub_launch_url
    assert "localhost" not in url
    assert url.startswith("http://130.185.73.157:8082/login?next=")
    # مسیر launch در next حفظ شده (رز هاب پس از ورود به آن برمی‌گردد)
    assert "clientId%3Drose-psy-5c3f9b" in url


def test_sso_full_chain_cookie_probe_refresh_me(client):
    """زنجیرهٔ کامل SSO: توکن رز هاب → کوکی refresh → پراپ → refresh → me.

    همین زنجیره‌ای است که مرورگر کاربر در بوت اسپای می‌رود؛ پیش از فاز ۷۲
    حلقهٔ پراپ→refresh وجود نداشت و کاربر در صفحهٔ ورود گیر می‌کرد.
    """
    _fresh_session(client)
    r = client.get(
        "/api/v1/auth/rose-sso",
        params={"sso_token": _hub_token()},
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text
    assert r.headers["location"] == "/panel"
    set_cookie = r.headers.get("set-cookie") or ""
    assert "rosepsy_refresh=" in set_cookie

    # پراپ نشست با کوکی — نشست زنده شناسایی می‌شود (بدون 401)
    probe = client.get("/api/v1/auth/session-probe")
    assert probe.status_code == 200
    assert probe.json()["authenticated"] is True
    assert probe.json()["must_change_password"] is False

    # بازیابی توکن با کوکی (کاری که اسپای در بوت می‌کند)
    refresh = client.post("/api/v1/auth/refresh")
    assert refresh.status_code == 200, refresh.text
    access = refresh.json()["access_token"]
    assert access

    # me با توکن بازیابی‌شده — هویت رز هاب کامل
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 200, me.text
    assert me.json()["email"] == EMAIL
    assert me.json()["display_name"] == "آزمون ورود یکپارچه فاز ۷۲"


def test_sso_probe_after_logout_is_false(client):
    """پس از خروج (ابطال نشست) پراپ دوباره False می‌شود — هیچ حالت گم‌شده‌ای نمی‌ماند."""
    _fresh_session(client)
    r = client.get(
        "/api/v1/auth/rose-sso",
        params={"sso_token": _hub_token()},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert client.get("/api/v1/auth/session-probe").json()["authenticated"] is True

    client.post("/api/v1/auth/logout")
    assert client.get("/api/v1/auth/session-probe").json() == {"authenticated": False}


def test_sso_probe_with_garbage_cookie_is_false(client):
    """کوکی نامعتبر/دست‌کاری‌شده → False با 200 — نه 500 و نه 401."""
    _fresh_session(client)
    client.cookies.set("rosepsy_refresh", "garbage-value")
    try:
        r = client.get("/api/v1/auth/session-probe")
        assert r.status_code == 200
        assert r.json() == {"authenticated": False}
    finally:
        _fresh_session(client)  # کوکی ساخته‌شدهٔ این آزمون به بعدی‌ها نریزد


def test_sso_probe_does_not_rotate_session(client):
    """پراپ اثر جانبی ندارد — نشست پس از پراپ همچنان برای refresh سالم است."""
    _fresh_session(client)
    client.get(
        "/api/v1/auth/rose-sso",
        params={"sso_token": _hub_token()},
        follow_redirects=False,
    )
    assert client.get("/api/v1/auth/session-probe").json()["authenticated"] is True
    # refresh پس از پراپ کار می‌کند (توکن چرخانده نشده)
    assert client.post("/api/v1/auth/refresh").status_code == 200
