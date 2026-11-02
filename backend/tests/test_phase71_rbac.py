"""فاز ۷۱ — ماتریس دسترسی منوها/زیرمنوها (دیدن/خواندن/ویرایش) + جداسازی آزمون‌ها.

قفل‌شدن چهار لایه:
۱) seed پیش‌فرض: وضعیت فعلی منوهای هر نقش دقیقاً بازتولید می‌شود (هیچ‌کس منو
   از دست نمی‌دهد) — RECEPTION applicants:edit، COUNSELOR worklist:edit، …
۲) /auth/me → menu_permissions برای فیلتر منوی پنل؛
۳) دروازهٔ سرور: GET فهرست=دیدن، GET جزئیات=خواندن، تغییر=ویرایش — 403 فارسی؛
۴) جداسازی آزمون: کاربر غیرکارمند در /psych-attempts فقط آزمون‌های خودش را
   می‌بیند؛ کارکنان کل فهرست را.
"""
from fastapi.testclient import TestClient

from conftest import PASSWORD, bearer, login


def _menus_of(client: TestClient, token: str) -> dict:
    r = client.get("/api/v1/auth/me", headers=bearer(token))
    assert r.status_code == 200, r.text
    return r.json().get("menu_permissions") or {}


# ---------------------------------------------------------------------------
# ۱) کاتالوگ و seed پیش‌فرض
# ---------------------------------------------------------------------------

def test_menu_catalog_has_all_menus(client: TestClient, env):
    token = login(client, "t_admin")
    r = client.get("/api/v1/rbac/menu-catalog", headers=bearer(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] >= 35
    keys = [it["key"] for g in body["groups"] for it in g["items"]]
    assert len(keys) == len(set(keys)), "کلید منوها باید یکتا باشد"
    for expected in ("cases", "applicants", "users", "roles-permissions", "psych-attempts",
                     "counseling-files", "psych-tests", "wallet", "audit-events"):
        assert expected in keys
    # سطح‌های سه‌گانه در کاتالوگ معرفی شده‌اند
    assert {lv["value"] for lv in body["levels"]} == {"view", "read", "edit"}


def test_default_seed_replicates_current_menus(client: TestClient, env):
    """پس از استقرار هیچ‌کس منویی را از دست نمی‌دهد."""
    rec = _menus_of(client, login(client, "t_reception"))
    assert rec.get("applicants") == "edit"
    assert rec.get("cases") == "edit"
    assert rec.get("psych-attempts") == "edit"
    assert rec.get("counseling-files") == "edit"
    assert rec.get("services") == "read"  # پذیرش خدمات را فقط می‌خواند
    assert "users" not in rec  # کاربران فقط SYSTEM_ADMIN
    assert "audit-events" not in rec

    cou = _menus_of(client, login(client, "t_counsa"))
    assert cou.get("worklist") == "edit"
    assert cou.get("cases") == "edit"
    assert cou.get("psych-attempts") == "read"
    assert "applicants" not in cou

    sup = _menus_of(client, login(client, "t_super"))
    assert sup.get("reviews") == "edit"
    assert sup.get("level3-alerts") == "edit"

    app = _menus_of(client, login(client, "t_appa"))
    assert app.get("psych-tests") == "edit"
    assert app.get("wallet") == "edit"
    # فاز ۷۱: متقاضی فهرست آزمون‌های برگزارشده را با سطح «دیدن» می‌بیند —
    # سمت سرور فقط آزمون‌های خودش را برمی‌گرداند
    assert app.get("psych-attempts") == "view"
    assert "cases" not in app
    assert "applicants" not in app


def test_system_admin_menu_permissions_full(client: TestClient, env):
    menus = _menus_of(client, login(client, "t_admin"))
    assert menus and all(lv == "edit" for lv in menus.values())
    assert "users" in menus and "audit-events" in menus


# ---------------------------------------------------------------------------
# ۲) API ماتریس: خواندن/ذخیره/اعتبارسنجی/قفل SYSTEM_ADMIN
# ---------------------------------------------------------------------------

def test_role_menus_get_put_roundtrip(client: TestClient, env):
    token = login(client, "t_admin")
    r = client.get("/api/v1/rbac/roles/RECEPTION/menus", headers=bearer(token))
    assert r.status_code == 200
    assert r.json()["locked"] is False
    assert r.json()["menus"]["applicants"] == "edit"

    # تغییر applicants به «فقط خواندن» و حذف imports
    r = client.put(
        "/api/v1/rbac/roles/RECEPTION/menus",
        headers=bearer(token),
        json={"menus": {"applicants": "read", "imports": None}},
    )
    assert r.status_code == 200, r.text
    assert r.json()["menus"]["applicants"] == "read"
    assert "imports" not in r.json()["menus"]
    # رخداد حسابرسی ثبت شده باشد
    ev = client.get(
        "/api/v1/audit-events", headers=bearer(token), params={"q": "rbac.role_menus_updated"}
    )
    assert ev.status_code == 200

    # بازگرداندن وضعیت پیش‌فرض برای بقیهٔ آزمون‌ها
    r = client.put(
        "/api/v1/rbac/roles/RECEPTION/menus",
        headers=bearer(token),
        json={"menus": {"applicants": "edit", "imports": "edit"}},
    )
    assert r.status_code == 200


def test_role_menus_validation_and_lock(client: TestClient, env):
    token = login(client, "t_admin")
    # کلید منوی ناشناخته
    r = client.put(
        "/api/v1/rbac/roles/RECEPTION/menus", headers=bearer(token),
        json={"menus": {"no_such_menu": "edit"}},
    )
    assert r.status_code == 422
    assert "نامعتبر" in r.json()["detail"]
    # سطح نامعتبر
    r = client.put(
        "/api/v1/rbac/roles/RECEPTION/menus", headers=bearer(token),
        json={"menus": {"cases": "admin"}},
    )
    assert r.status_code == 422
    # نقش SYSTEM_ADMIN قفل است
    r = client.put(
        "/api/v1/rbac/roles/SYSTEM_ADMIN/menus", headers=bearer(token),
        json={"menus": {"cases": "view"}},
    )
    assert r.status_code == 422
    assert "SYSTEM_ADMIN" in r.json()["detail"]
    # GET ماتریس SYSTEM_ADMIN → همه edit + locked
    r = client.get("/api/v1/rbac/roles/SYSTEM_ADMIN/menus", headers=bearer(token))
    assert r.status_code == 200
    assert r.json()["locked"] is True


def test_non_admin_cannot_edit_menu_matrix(client: TestClient, env):
    token = login(client, "t_manager")
    r = client.put(
        "/api/v1/rbac/roles/RECEPTION/menus", headers=bearer(token),
        json={"menus": {"cases": "view"}},
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# ۳) اجرای عملی سطوح: دیدن / خواندن / ویرایش روی /cases
# ---------------------------------------------------------------------------

def test_view_level_allows_list_blocks_detail_and_edit(client: TestClient, env):
    admin = login(client, "t_admin")
    rec = login(client, "t_reception")

    # پذیرش پیش‌فرض edit دارد → همه‌چیز باز
    r = client.get("/api/v1/cases", headers=bearer(rec))
    assert r.status_code == 200

    # تقلیل به «دیدن»: فهرست باز، جزئیات و تغییر بسته
    client.put("/api/v1/rbac/roles/RECEPTION/menus", headers=bearer(admin),
               json={"menus": {"cases": "view"}})
    r = client.get("/api/v1/cases", headers=bearer(rec))
    assert r.status_code == 200, "سطح دیدن باید فهرست را باز کند"
    case_id = env["case"].id
    r = client.get(f"/api/v1/cases/{case_id}", headers=bearer(rec))
    assert r.status_code == 403, "سطح دیدن نباید جزئیات را باز کند"
    assert "کافی نیست" in r.json()["detail"]
    r = client.post("/api/v1/cases", headers=bearer(rec), json={})
    assert r.status_code == 403, "سطح دیدن نباید اجازهٔ ثبت بدهد"

    # ارتقا به «فقط خواندن»: جزئیات باز، تغییر بسته
    client.put("/api/v1/rbac/roles/RECEPTION/menus", headers=bearer(admin),
               json={"menus": {"cases": "read"}})
    r = client.get(f"/api/v1/cases/{case_id}", headers=bearer(rec))
    assert r.status_code == 200, "سطح خواندن باید جزئیات را باز کند"
    r = client.post("/api/v1/cases", headers=bearer(rec), json={})
    assert r.status_code == 403

    # بازگرداندن به edit
    client.put("/api/v1/rbac/roles/RECEPTION/menus", headers=bearer(admin),
               json={"menus": {"cases": "edit"}})
    r = client.get("/api/v1/cases", headers=bearer(rec))
    assert r.status_code == 200


def test_none_level_blocks_section_entirely(client: TestClient, env):
    admin = login(client, "t_admin")
    rec = login(client, "t_reception")
    client.put("/api/v1/rbac/roles/RECEPTION/menus", headers=bearer(admin),
               json={"menus": {"imports": None}})
    r = client.get("/api/v1/imports", headers=bearer(rec))
    assert r.status_code == 403
    r = client.post("/api/v1/imports/applicants/preview", headers=bearer(rec), json={})
    assert r.status_code == 403
    client.put("/api/v1/rbac/roles/RECEPTION/menus", headers=bearer(admin),
               json={"menus": {"imports": "edit"}})
    r = client.get("/api/v1/imports", headers=bearer(rec))
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# ۴) جداسازی آزمون: هر کاربر فقط آزمون‌های خودش
# ---------------------------------------------------------------------------

def test_non_staff_sees_only_own_attempts(client: TestClient, env):
    from app.models.psych_test import PsychAttempt, PsychTest

    db = env["db"]
    test = PsychTest(
        slug="p71-isolation", title="آزمون جداسازی فاز ۷۱", status="published",
    )
    db.add(test)
    db.flush()
    app_a = env["applicant_a"].user_id  # t_appa
    # کاربر دوم متقاضی
    from app.models.user import Role, User, UserStatus
    from app.core.security import hash_password

    ub = User(username="t_appb", display_name="متقاضی بی", status=UserStatus.ACTIVE,
              must_change_password=False)
    ub.password_hash = hash_password(PASSWORD)
    ub.roles.append(db.get(Role, "APPLICANT"))
    db.add(ub)
    db.flush()
    a1 = PsychAttempt(test_id=test.id, user_id=app_a, score=10, interpretation_label="متوسط")
    a2 = PsychAttempt(test_id=test.id, user_id=ub.id, score=20, interpretation_label="بالا")
    db.add_all([a1, a2])
    db.commit()

    tok_a = login(client, "t_appa")
    r = client.get("/api/v1/psych-attempts", headers=bearer(tok_a))
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    ids = {it["id"] for it in items}
    assert str(a1.id) in ids
    assert str(a2.id) not in ids, "متقاضی نباید آزمون کاربر دیگر را ببیند"
    assert all(it.get("user_username") == "t_appa" for it in items)

    # کاربر دوم هم فقط خودش
    tok_b = login(client, "t_appb")
    r = client.get("/api/v1/psych-attempts", headers=bearer(tok_b))
    ids_b = {it["id"] for it in r.json()["items"]}
    assert str(a2.id) in ids_b and str(a1.id) not in ids_b

    # کارکنان: فهرست کامل هر دو
    for uname in ("t_admin", "t_reception", "t_counsa", "t_super"):
        tok = login(client, uname)
        r = client.get("/api/v1/psych-attempts", headers=bearer(tok))
        assert r.status_code == 200
        ids_s = {it["id"] for it in r.json()["items"]}
        assert str(a1.id) in ids_s and str(a2.id) in ids_s, f"کارمند {uname} باید هر دو را ببیند"
