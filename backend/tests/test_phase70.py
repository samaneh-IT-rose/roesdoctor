"""فاز ۷۰ - پروندهٔ مشاورهٔ کاربر + تاریخچهٔ آزمون/مشاوره + چت سالم + عامل اقدام‌محور.

- رگرسیون چت عمومی: هر پیام باید ۲۰۱ برگرداند (باگ میدانی فاز ۵۶:
  NameError ثابت‌های مدل → ۵۰۰ → «خطا در ارسال پیام» برای همهٔ پیام‌ها)؛
- حضور اپراتور → سکوت دستیار (message=null)؛
- عامل بدون کلید LLM حالا اقدام‌محور است: رزرو → مشاوران واقعی؛ ثبت درخواست؛
- لیست «آزمون‌های برگزارشده» با هویت آزمون‌دهنده؛
- «ایجاد پرونده» از روی آزمون → متقاضی + پرونده + اتصال همهٔ آزمون‌ها؛
- نتایج دیده‌شده (viewed_at) و پروندهٔ مشاورهٔ خودکار هر کاربر.
"""
import uuid as _uuid

import pytest

from conftest import bearer, login


# =========================================================== چت عمومی
def test_public_chat_send_all_intents_ok(client, env):
    """رگرسیون فاز ۷۰: قبل از فیکس همهٔ پیام‌ها ۵۰۰ می‌شد (NameError)."""
    token = "p70" + _uuid.uuid4().hex[:12]
    r = client.post("/api/v1/public/chat/session", json={"token": token, "visitor_name": "تستر۷۰"})
    assert r.status_code == 200, r.text
    for msg, expected_intent in [
        ("میخوام نوبت بگیرم", "booking"),
        ("قیمت خدمات چنده؟", "pricing"),
        ("مشاوران شما چه کسانی هستند؟", "counselors"),
        ("سلام", "greeting"),
        ("asdf qwer 123", "fallback"),
    ]:
        r = client.post(f"/api/v1/public/chat/{token}/messages", json={"content": msg})
        assert r.status_code == 201, f"{msg} → {r.status_code}: {r.text}"
        d = r.json()
        assert d["message"] is not None
        assert d["message"]["intent"] == expected_intent, msg
    # کارت اقدام نیت رزرو از DB واقعی می‌آید
    r = client.post(f"/api/v1/public/chat/{token}/messages", json={"content": "نوبت برای مشاور"})
    actions = r.json()["message"]["actions"] or []
    assert any(a.get("kind") == "counselor" for a in actions) or any(
        a.get("url") == "/booking" for a in actions)


def test_public_chat_operator_takeover_silences_assistant(client, env):
    admin = bearer(login(client, "t_admin"))
    token = "p70" + _uuid.uuid4().hex[:12]
    who = "اپراتور-" + _uuid.uuid4().hex[:6]
    r = client.post("/api/v1/public/chat/session", json={"token": token, "visitor_name": who})
    assert r.status_code == 200
    # پیام اول — دستیار پاسخ می‌دهد
    r = client.post(f"/api/v1/public/chat/{token}/messages", json={"content": "سلام"})
    assert r.status_code == 201 and r.json()["message"] is not None
    # اپراتور پاسخ می‌دهد → دستیار ساکت می‌شود (نشست با نام یکتا پیدا می‌شود)
    sessions = client.get(f"/api/v1/public-chat/admin/sessions?q={who}", headers=admin).json()
    sid = next(s["id"] for s in sessions["items"] if s["visitor_name"] == who)
    r = client.post(f"/api/v1/public-chat/admin/sessions/{sid}/reply",
                    headers=admin, json={"content": "خودم پیگیری می‌کنم"})
    assert r.status_code == 201, r.text
    r = client.post(f"/api/v1/public/chat/{token}/messages", json={"content": "ممنون"})
    assert r.status_code == 201
    assert r.json()["message"] is None  # دستیار ساکت


# =========================================================== عامل اقدام‌محور
@pytest.fixture()
def _clear_ai_rate_limit():
    """سقف نرخ دستیار in-process برای کاربران آزمون پاک می‌شود
    (test_phase35 عمداً سقف t_appa را پر می‌کند)."""
    from app.services import ai_assistant

    ai_assistant._rate_bucket.clear()
    yield
    ai_assistant._rate_bucket.clear()


def test_agent_rule_mode_books_and_runs_tools(client, env, _clear_ai_rate_limit):
    """بدون کلید LLM هم گفتگو قابلیت واقعی دارد (فاز ۷۰)."""
    r = client.post("/api/v1/ai/agent/chat",
                    headers=bearer(login(client, "t_appa")),
                    json={"message": "می‌خواهم نوبت رزرو کنم", "session_id": None})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["fallback_used"] is True
    assert any(s["tool_name"] == "find_counselor" for s in d["steps"])
    # مشاور صلاحیت‌دار seed همگام در پاسخ ظاهر می‌شود
    assert "رزرو" in d["response"]


def test_agent_rule_mode_booking_request_write(client, env, _clear_ai_rate_limit):
    """الگوی «ثبت درخواست مشاوره برای نام ۰۹…» → درخواست واقعی ثبت می‌شود."""
    r = client.post("/api/v1/ai/agent/chat",
                    headers=bearer(login(client, "t_reception")),
                    json={"message": "ثبت درخواست مشاوره برای علی احمدی 09121234070", "session_id": None})
    assert r.status_code == 200, r.text
    assert "✅" in r.json()["response"]
    mgr = bearer(login(client, "t_manager"))
    r = client.get("/api/v1/consultation-requests?status=new", headers=mgr)
    assert r.status_code == 200, r.text
    assert any(x["mobile"] == "09121234070" for x in r.json()["items"])


# =========================================================== آزمون‌ها
def _mk_published_test(client, manager, supervisor) -> dict:
    suffix = _uuid.uuid4().hex[:8]
    r = client.post("/api/v1/psych-tests", headers=manager, json={
        "slug": f"p70-{suffix}", "title": f"ابزار ف۷۰ {suffix}", "description": "تست فاز ۷۰",
    })
    assert r.status_code == 201, r.text
    t = r.json()
    r = client.post(f"/api/v1/psych-tests/{t['id']}/questions", headers=manager, json={
        "prompt": "سؤال ۱",
        "options": [{"label": "هیچ", "score": 0}, {"label": "زیاد", "score": 3}],
        "sort_order": 0,
    })
    assert r.status_code == 201, r.text
    r = client.post(f"/api/v1/psych-tests/{t['id']}/interpretations", headers=manager, json={
        "score_min": 0, "score_max": 3, "label": "سطح پایه", "guidance": "توصیه آزمایشی",
    })
    assert r.status_code == 201, r.text
    client.post(f"/api/v1/psych-tests/{t['id']}/submit-review", headers=manager)
    r = client.post(f"/api/v1/psych-tests/{t['id']}/review", headers=supervisor,
                    json={"approve": True, "note": "تأیید علمی"})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture()
def psych_env(client, env):
    """کاربر اختصاصی فاز ۷۰ + ابزار منتشرشده + یک اجرا —
    (t_appa اشتراکی است و پروندهٔ قبلی دارد؛ برای تست پرونده‌سازی کاربر تازه می‌سازیم)."""
    from sqlalchemy import select

    from app.core.security import hash_password
    from app.db.session import SessionLocal
    from app.models.user import Role, User, UserStatus

    from conftest import PASSWORD

    uname = "p70u" + _uuid.uuid4().hex[:6]
    mobile = "0912" + "".join(str(_uuid.uuid4().int % 10) for _ in range(7))
    db = SessionLocal()
    u = User(username=uname, display_name="آزمون‌دهنده ف۷۰", mobile=mobile,
             password_hash=hash_password(PASSWORD), status=UserStatus.ACTIVE,
             must_change_password=False)
    u.roles.append(db.get(Role, "APPLICANT"))
    db.add(u)
    db.commit()
    db.close()

    manager = bearer(login(client, "t_manager"))
    supervisor = bearer(login(client, "t_super"))
    applicant = bearer(login(client, uname))
    t = _mk_published_test(client, manager, supervisor)
    r = client.post(f"/api/v1/public/psych-tests/{t['slug']}/attempts", headers=applicant,
                    json={"answers": [1]})
    assert r.status_code == 201, r.text
    attempt = r.json()["attempt"]
    return {"manager": manager, "supervisor": supervisor, "applicant": applicant,
            "reception": bearer(login(client, "t_reception")),
            "test": t, "attempt": attempt, "username": uname}


def test_results_viewed_marking(client, env, psych_env):
    aid = psych_env["attempt"]["id"]
    assert psych_env["attempt"]["viewed_at"] is None
    r = client.get("/api/v1/my/psych-results", headers=psych_env["applicant"])
    assert r.status_code == 200 and len(r.json()["items"]) >= 1
    r = client.get(f"/api/v1/my/psych-results/{aid}/viewed", headers=psych_env["applicant"])
    assert r.status_code == 405  # GET مجاز نیست — ثبت فقط با POST
    r = client.post(f"/api/v1/my/psych-results/{aid}/viewed", headers=psych_env["applicant"])
    assert r.status_code == 200 and r.json()["viewed_at"]
    # دوباره — زمان اولین بازدید دست نمی‌خورد
    r2 = client.post(f"/api/v1/my/psych-results/{aid}/viewed", headers=psych_env["applicant"])
    assert r2.json()["viewed_at"] == r.json()["viewed_at"]


def test_staff_attempts_list_shows_person(client, env, psych_env):
    r = client.get("/api/v1/psych-attempts", headers=psych_env["reception"])
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert items, "لیست آزمون‌های برگزارشده خالی است"
    row = next(x for x in items if x["id"] == psych_env["attempt"]["id"])
    assert row["test_title"].startswith("ابزار ف۷۰")
    assert row["user_display_name"] == "آزمون‌دهنده ف۷۰"
    assert row["user_username"] == psych_env["username"]
    assert row["case_number"] is None
    # فیلتر جست‌وجو
    r = client.get(f"/api/v1/psych-attempts?q={psych_env['username']}", headers=psych_env["reception"])
    assert any(x["id"] == psych_env["attempt"]["id"] for x in r.json()["items"])


def test_create_case_from_attempt_links_all(client, env, psych_env):
    aid = psych_env["attempt"]["id"]
    r = client.post(f"/api/v1/psych-attempts/{aid}/create-case", headers=psych_env["reception"], json={})
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["case_created"] is True and d["linked_attempts"] >= 1
    assert d["case_number"].startswith("RS-")
    # پروندهٔ مشاورهٔ آزمون‌دهنده در دسترس کارکنان است
    r = client.get(f"/api/v1/counseling-files/{psych_env['attempt']['user_id']}",
                   headers=psych_env["reception"])
    assert r.status_code == 200, r.text
    # فراخوانی دوباره — پروندهٔ همان قبلی، بدون اتصال تکراری
    r2 = client.post(f"/api/v1/psych-attempts/{aid}/create-case", headers=psych_env["reception"], json={})
    assert r2.status_code == 201
    assert r2.json()["case_created"] is False
    assert r2.json()["case_id"] == d["case_id"]
    # تب نتایج آزمون پرونده
    r = client.get(f"/api/v1/cases/{d['case_id']}/psych-attempts", headers=psych_env["reception"])
    assert r.status_code == 200 and len(r.json()["items"]) >= 1
    # در لیست سراسری هم شمارهٔ پرونده دیده می‌شود
    r = client.get("/api/v1/psych-attempts", headers=psych_env["reception"])
    row = next(x for x in r.json()["items"] if x["id"] == aid)
    assert row["case_number"] == d["case_number"]


def test_counseling_file_auto_and_timeline(client, env, psych_env):
    """پروندهٔ مشاورهٔ خودکار + تاریخچهٔ آزمون با زمان + نتایج دیده‌شده."""
    app_h = psych_env["applicant"]
    r = client.get("/api/v1/me/counseling-file", headers=app_h)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["file"]["file_code"].startswith("UF-")
    assert d["counts"]["psych_tests"] >= 1
    kinds = [i["kind"] for i in d["items"]]
    assert "psych_test" in kinds
    item = next(i for i in d["items"] if i["kind"] == "psych_test")
    assert item["title"].startswith("ابزار ف۷۰") and item["at"]
    # پرونده برای کاربر بدون آزمون هم در دسترس است (خالی)
    r = client.get("/api/v1/me/counseling-file", headers=bearer(login(client, "t_counsa")))
    assert r.status_code == 200 and r.json()["counts"]["psych_tests"] == 0
    # فهرست کارکنان
    r = client.get(f"/api/v1/counseling-files?q={psych_env['username']}", headers=psych_env["reception"])
    assert r.status_code == 200, r.text
    assert any(x["attempt_count"] >= 1 for x in r.json()["items"])


def test_counseling_file_links_consultations_by_mobile(client, env):
    """درخواست مشاوره با موبایل حساب → در تاریخچهٔ همان کاربر ظاهر می‌شود."""
    from sqlalchemy import select

    from app.core.security import hash_password
    from app.db.session import SessionLocal
    from app.models.user import Role, User, UserStatus

    from conftest import PASSWORD

    db = SessionLocal()
    mobile = "09121234071"
    guest = db.scalar(select(User).where(User.username == mobile))
    if guest is None:
        guest = User(username=mobile, display_name="مهمان رزرو ف۷۰", mobile=mobile,
                     password_hash=hash_password(PASSWORD), status=UserStatus.ACTIVE,
                     must_change_password=False)
        guest.roles.append(db.get(Role, "APPLICANT"))
        db.add(guest)
        db.commit()
    db.close()

    mgr = bearer(login(client, "t_manager"))
    r = client.post("/api/v1/consultation-requests", headers=mgr, json={
        "full_name": "مهمان رزرو ف۷۰", "mobile": mobile, "topic": "مشاوره فردی",
    })
    assert r.status_code == 201, r.text

    token = bearer(login(client, mobile))
    r = client.get("/api/v1/me/counseling-file", headers=token)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["counts"]["consultations"] >= 1, "درخواست مشاورهٔ هم‌موبایل در تاریخچه نیست"
    kinds = [i["kind"] for i in d["items"]]
    assert "consultation" in kinds
