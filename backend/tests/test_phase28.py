"""فاز ۲۸ - B05/B06/B07 سند جامع: صلاحیت مشاور، خدمات و تعرفه نسخه‌دار.

- B05: مشاور بدون صلاحیت معتبر در فهرست قابل رزرو (عمومی) قرار نمی‌گیرد؛
  مدرک تأییدشده → قابل رزرو، منقضی/رد‌شده → غیرقابل رزرو.
- B06: مدت خدمت مثبت؛ خدمت غیرفعال رزرو جدید نمی‌گیرد.
- B07: هم‌پوشانی بازه‌های تعرفه رد می‌شود؛ قیمت نوبت گذشته با تغییر تعرفه
  تغییر نمی‌کند (snapshot).
"""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from app.api.v1 import public as public_mod
from app.models.catalog import Service, Specialty

from conftest import bearer, login


@pytest.fixture(autouse=True)
def _clear_rate_limiter():
    """لیمیت‌های درون‌حافظه‌ای مسیر عمومی پاک و نگهداشت‌های فعال تست‌های
    دیگر آزاد می‌شوند تا سقف hold-per-IP این آزمون‌ها را نگیرد."""
    public_mod._req_ip.clear()
    public_mod._hold_ip.clear()
    from app.db.session import SessionLocal
    from app.models.booking import SlotClaim, SlotClaimStatus

    db = SessionLocal()
    try:
        db.query(SlotClaim).filter(SlotClaim.status == SlotClaimStatus.ACTIVE).update(
            {"status": SlotClaimStatus.EXPIRED}
        )
        db.commit()
    finally:
        db.close()
    yield
    public_mod._req_ip.clear()
    public_mod._hold_ip.clear()


@pytest.fixture()
def manager_headers(client, env):
    return bearer(login(client, "t_manager"))


@pytest.fixture()
def supervisor_headers(client, env):
    return bearer(login(client, "t_super"))


@pytest.fixture()
def reception_headers(client, env):
    return bearer(login(client, "t_reception"))


def _mk_counselor(client, headers, code) -> dict:
    r = client.post("/api/v1/counselors", headers=headers, json={
        "counselor_code": code, "first_name": "فاز۲۸", "last_name": f"مشاور {code}",
    })
    assert r.status_code == 201, r.text
    return r.json()


def _add_credential(client, headers, counselor_id, **over) -> dict:
    payload = {"kind": "license", "title": "مجوز نظام روان‌شناسی", "license_number": "LIC-1"}
    payload.update(over)
    r = client.post(f"/api/v1/counselors/{counselor_id}/credentials", headers=headers, json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _review(client, headers, credential_id, action="approve", note=None) -> dict:
    r = client.post(f"/api/v1/verification-reviews/{credential_id}", headers=headers,
                    json={"action": action, "note": note})
    assert r.status_code == 200, r.text
    return r.json()


def _public_ids(client) -> set[str]:
    r = client.get("/api/v1/public/counselors")
    assert r.status_code == 200, r.text
    return {c["id"] for c in r.json()["items"]}


# ---------------- B05: صلاحیت مشاور ----------------

def test_unqualified_counselor_not_bookable(client, manager_headers):
    """B05 پذیرش: مشاور بدون صلاحیت معتبر در فهرست قابل رزرو قرار نمی‌گیرد."""
    c = _mk_counselor(client, manager_headers, "P28-A")
    assert c["bookable"] is False
    assert c["id"] not in _public_ids(client)
    r = client.get(f"/api/v1/public/booking/slots?counselor_id={c['id']}")
    assert r.status_code == 404
    # نگهداشت هم رد می‌شود
    r = client.post("/api/v1/public/booking-holds", json={
        "counselor_id": c["id"],
        "start_at": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
    })
    assert r.status_code == 422


def test_approved_credential_makes_counselor_bookable(client, manager_headers, supervisor_headers):
    """B05: مدرک در انتظار → غیرقابل رزرو؛ پس از تأیید → قابل رزرو."""
    c = _mk_counselor(client, manager_headers, "P28-B")
    cred = _add_credential(client, manager_headers, c["id"])
    assert cred["verification_status"] == "pending"
    assert c["id"] not in _public_ids(client)
    reviewed = _review(client, supervisor_headers, cred["id"], "approve")
    assert reviewed["verification_status"] == "approved"
    assert reviewed["reviewed_at"] is not None
    assert c["id"] in _public_ids(client)


def test_rejected_credential_not_bookable(client, manager_headers, supervisor_headers):
    c = _mk_counselor(client, manager_headers, "P28-C")
    cred = _add_credential(client, manager_headers, c["id"], title="مدرک ناقص")
    _review(client, supervisor_headers, cred["id"], "reject", note="نمونه مدرک بارگذاری نشده")
    assert c["id"] not in _public_ids(client)


def test_expired_credential_not_bookable(client, manager_headers, supervisor_headers):
    c = _mk_counselor(client, manager_headers, "P28-D")
    cred = _add_credential(client, manager_headers, c["id"],
                           issued_at=str(date.today() - timedelta(days=800)),
                           expires_at=str(date.today() - timedelta(days=1)))
    _review(client, supervisor_headers, cred["id"], "approve")
    assert c["id"] not in _public_ids(client)


def test_reception_cannot_review_credentials(client, reception_headers, manager_headers):
    c = _mk_counselor(client, manager_headers, "P28-E")
    cred = _add_credential(client, manager_headers, c["id"])
    r = client.post(f"/api/v1/verification-reviews/{cred['id']}", headers=reception_headers,
                    json={"action": "approve"})
    assert r.status_code == 403


def test_credential_expiry_before_issuance_rejected(client, manager_headers):
    c = _mk_counselor(client, manager_headers, "P28-F")
    r = client.post(f"/api/v1/counselors/{c['id']}/credentials", headers=manager_headers, json={
        "kind": "license", "title": "مجوز",
        "issued_at": str(date.today()), "expires_at": str(date.today() - timedelta(days=1)),
    })
    assert r.status_code == 422


def test_verification_review_list_pending(client, manager_headers, supervisor_headers):
    c = _mk_counselor(client, manager_headers, "P28-G")
    _add_credential(client, manager_headers, c["id"], title="مجوز فهرست")
    r = client.get("/api/v1/verification-reviews?status=pending", headers=supervisor_headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(x["counselor_id"] == c["id"] for x in items)


# ---------------- B06: خدمات و تخصص‌ها ----------------

def test_specialty_and_service_lifecycle(client, manager_headers, reception_headers):
    r = client.post("/api/v1/specialties", headers=manager_headers,
                    json={"name": "فاز۲۸-اضطراب", "description": "تخصص آزمون"})
    assert r.status_code == 201, r.text
    sp = r.json()
    # نام تکراری رد می‌شود
    r = client.post("/api/v1/specialties", headers=manager_headers, json={"name": "فاز۲۸-اضطراب"})
    assert r.status_code == 409
    # مدت غیرمثبت رد می‌شود (B06)
    r = client.post("/api/v1/services", headers=manager_headers, json={
        "specialty_id": sp["id"], "title": "جلسه فردی", "duration_minutes": 0,
    })
    assert r.status_code == 422
    # ساخت خدمت معتبر
    r = client.post("/api/v1/services", headers=manager_headers, json={
        "specialty_id": sp["id"], "title": "جلسه درمان فردی فاز۲۸",
        "duration_minutes": 45, "session_type": "in_person", "code": "SVC-P28",
    })
    assert r.status_code == 201, r.text
    svc = r.json()
    assert svc["status"] == "active" and svc["duration_minutes"] == 45
    # پذیرش می‌تواند فهرست کند
    r = client.get("/api/v1/services", headers=reception_headers)
    assert r.status_code == 200
    assert any(x["id"] == svc["id"] for x in r.json()["items"])
    # نوع جلسه نامعتبر
    r = client.post("/api/v1/services", headers=manager_headers, json={
        "specialty_id": sp["id"], "title": "جلسه س", "duration_minutes": 30, "session_type": "carrier",
    })
    assert r.status_code == 422


def test_inactive_service_receives_no_new_booking(client, manager_headers):
    """B06 پذیرش: خدمت غیرفعال رزرو جدید نمی‌گیرد (مسیر عمومی و کارکنان)."""
    r = client.post("/api/v1/specialties", headers=manager_headers, json={"name": "فاز۲۸-خانواده"})
    assert r.status_code == 201
    sp = r.json()
    r = client.post("/api/v1/services", headers=manager_headers, json={
        "specialty_id": sp["id"], "title": "درمان زوج‌درمانی فاز۲۸", "duration_minutes": 60,
    })
    svc = r.json()
    # فعال → در فهرست عمومی هست و رزرو با آن ممکن است
    r = client.get("/api/v1/public/services")
    assert r.status_code == 200
    assert any(x["id"] == svc["id"] for x in r.json()["items"])
    r = client.post("/api/v1/public/consultation-requests", json={
        "full_name": "مراجع فاز۲۸", "mobile": "09121110000", "topic": "مشاوره زوج",
        "service_id": svc["id"],
    })
    assert r.status_code == 201, r.text
    # غیرفعال‌سازی
    r = client.patch(f"/api/v1/services/{svc['id']}", headers=manager_headers,
                     json={"status": "inactive"})
    assert r.status_code == 200
    # از فهرست عمومی حذف و رزرو جدید رد می‌شود
    r = client.get("/api/v1/public/services")
    assert not any(x["id"] == svc["id"] for x in r.json()["items"])
    r = client.post("/api/v1/public/consultation-requests", json={
        "full_name": "مراجع فاز۲۸", "mobile": "09121110001", "topic": "مشاوره زوج",
        "service_id": svc["id"],
    })
    assert r.status_code == 409
    # نوبت کارکنان با خدمت غیرفعال هم رد می‌شود
    case_id = client.get("/api/v1/cases?page_size=1", headers=manager_headers).json()["items"][0]["id"]
    r = client.post("/api/v1/appointments", headers=manager_headers, json={
        "case_id": case_id,
        "service_id": svc["id"],
        "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
    })
    assert r.status_code == 409


# ---------------- B07: تعرفه نسخه‌دار ----------------

@pytest.fixture()
def _tariff_fixtures(client, manager_headers):
    """هر آزمون تعرفه، خدمت اختصاصی خودش را دارد تا بازه‌ها تداخل نکنند."""
    suffix = uuid.uuid4().hex[:6]
    r = client.post("/api/v1/specialties", headers=manager_headers, json={"name": f"فاز۲۸-تعرفه-{suffix}"})
    assert r.status_code == 201, r.text
    sp = r.json()
    r = client.post("/api/v1/services", headers=manager_headers, json={
        "specialty_id": sp["id"], "title": f"خدمت تعرفه‌دار فاز۲۸-{suffix}", "duration_minutes": 50,
    })
    assert r.status_code == 201, r.text
    return r.json()


def _mk_tariff(client, headers, service_id, amount, vf, vt=None, currency="IRR") -> dict:
    payload = {"service_id": service_id, "amount": amount, "valid_from": vf, "currency": currency}
    if vt:
        payload["valid_to"] = vt
    r = client.post("/api/v1/tariffs", headers=headers, json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def test_tariff_overlap_rejected(client, manager_headers, _tariff_fixtures):
    """B07 پذیرش: هم‌پوشانی ناسازگار بازه‌ها رد شود."""
    svc = _tariff_fixtures
    # ماه ثابت ۳۱روزه (ژانویهٔ سال بعد) — آزمون مستقل از تقویم؛ «ماه جاری» در
    # ماه‌های ۳۰روزه/اسفند روی روز ۳۱ می‌شکست (422 تاریخ نامعتبر، آبان ۱۴۰۵).
    y, m = date.today().year + 1, 1
    v1 = _mk_tariff(client, manager_headers, svc["id"], 500000, f"{y}-{m:02d}-01", f"{y}-{m:02d}-28")
    # هم‌پوشانی کامل و جزئی رد می‌شود
    r = client.post("/api/v1/tariffs", headers=manager_headers, json={
        "service_id": svc["id"], "amount": 600000,
        "valid_from": f"{y}-{m:02d}-10", "valid_to": f"{y}-{m:02d}-20",
    })
    assert r.status_code == 409
    r = client.post("/api/v1/tariffs", headers=manager_headers, json={
        "service_id": svc["id"], "amount": 700000,
        "valid_from": f"{y}-{m:02d}-28", "valid_to": f"{y}-{m:02d}-30",
    })
    assert r.status_code == 409  # هم‌پوشانی مرزی (شمول دو سر روز)
    # بازه مجاور مجاز است
    v2 = _mk_tariff(client, manager_headers, svc["id"], 650000, f"{y}-{m:02d}-29", f"{y}-{m:02d}-31")
    assert v2["valid_from"] == f"{y}-{m:02d}-29"
    # مبلغ نسخه منتشرشده تغییر نمی‌کند (PATCH مبلغ ندارد)
    r = client.patch(f"/api/v1/tariffs/{v1['id']}", headers=manager_headers, json={"note": "تعدیل"})
    assert r.status_code == 200


def test_pricing_quote_by_date(client, manager_headers, _tariff_fixtures):
    svc = _tariff_fixtures
    y, m = date.today().year + 1, date.today().month
    _mk_tariff(client, manager_headers, svc["id"], 400000, f"{y}-01-01", f"{y}-06-30")
    _mk_tariff(client, manager_headers, svc["id"], 450000, f"{y}-07-01", f"{y}-12-30")
    r = client.get(f"/api/v1/pricing/quote?service_id={svc['id']}&date={y}-03-15", headers=manager_headers)
    assert r.status_code == 200, r.text
    assert r.json()["amount"] == 400000
    r = client.get(f"/api/v1/pricing/quote?service_id={svc['id']}&date={y}-08-15", headers=manager_headers)
    assert r.json()["amount"] == 450000
    # تاریخ بدون تعرفه
    r = client.get(f"/api/v1/pricing/quote?service_id={svc['id']}&date={y - 1}-01-15", headers=manager_headers)
    assert r.status_code == 404


def test_tariff_manage_role_required(client, reception_headers, manager_headers, _tariff_fixtures):
    r = client.get(f"/api/v1/tariffs?service_id={_tariff_fixtures['id']}", headers=reception_headers)
    assert r.status_code == 200
    r = client.post("/api/v1/tariffs", headers=reception_headers, json={
        "service_id": _tariff_fixtures["id"], "amount": 100000,
        "valid_from": str(date.today() + timedelta(days=400)),
    })
    assert r.status_code == 403


def test_open_ended_tariff_blocks_successor_until_closed(client, manager_headers, _tariff_fixtures):
    svc = _tariff_fixtures
    y = date.today().year + 2
    v1 = _mk_tariff(client, manager_headers, svc["id"], 300000, f"{y}-01-01")
    r = client.post("/api/v1/tariffs", headers=manager_headers, json={
        "service_id": svc["id"], "amount": 350000, "valid_from": f"{y}-07-01",
    })
    assert r.status_code == 409
    # بستن نسخه باز-پایان و افزودن نسخه بعدی
    r = client.patch(f"/api/v1/tariffs/{v1['id']}", headers=manager_headers,
                     json={"valid_to": f"{y}-06-30"})
    assert r.status_code == 200, r.text
    v2 = _mk_tariff(client, manager_headers, svc["id"], 350000, f"{y}-07-01")
    assert v2["amount"] == 350000


def test_appointment_price_snapshot_immutable(client, manager_headers):
    """B07 پذیرش: قیمت سفارش گذشته تغییر نکند (snapshot روی نوبت)."""
    # خدمت + تعرفه نسخه اول
    r = client.post("/api/v1/specialties", headers=manager_headers, json={"name": "فاز۲۸-اسنپ‌شات"})
    sp = r.json()
    r = client.post("/api/v1/services", headers=manager_headers, json={
        "specialty_id": sp["id"], "title": "خدمت snapshot فاز۲۸", "duration_minutes": 40,
    })
    svc = r.json()
    future = (date.today() + timedelta(days=21))
    far = future + timedelta(days=10)
    _mk_tariff(client, manager_headers, svc["id"], 250000, str(future), str(future + timedelta(days=5)))
    # نوبت با خدمت → قیمت از تعرفه همان تاریخ
    m = bearer(login(client, "t_manager"))
    case_id = client.get("/api/v1/cases?page_size=1", headers=m).json()["items"][0]["id"]
    sched = datetime.combine(future, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=9)
    r = client.post("/api/v1/appointments", headers=m, json={
        "case_id": case_id, "service_id": svc["id"], "scheduled_at": sched.isoformat(),
    })
    assert r.status_code == 201, r.text
    appt = r.json()
    assert appt["price_amount"] == 250000 and appt["price_currency"] == "IRR"
    assert appt["service_title"] == "خدمت snapshot فاز۲۸"
    assert appt["duration_minutes"] == 40  # مدت پیش‌فرض از خدمت
    # تعرفه جدید برای همان تاریخ قبلی ممکن نیست (هم‌پوشانی)؛ اکنون قیمت نوبت
    # ثبت‌شده حتی پس از افزودن تعرفه‌های جدید بدون تغییر می‌ماند (snapshot)
    _mk_tariff(client, manager_headers, svc["id"], 999000, str(future + timedelta(days=6)), str(far))
    r = client.get(f"/api/v1/appointments?case_id={case_id}", headers=m)
    assert r.status_code == 200
    row = next(x for x in r.json()["items"] if x["id"] == appt["id"])
    assert row["price_amount"] == 250000
    # استعلام امروز تاریخ جدید → قیمت جدید؛ ولی snapshot نوبت دست‌نخورده
    r = client.get(f"/api/v1/pricing/quote?service_id={svc['id']}&date={future + timedelta(days=6)}", headers=m)
    assert r.json()["amount"] == 999000
    r = client.get(f"/api/v1/appointments?case_id={case_id}", headers=m)
    row = next(x for x in r.json()["items"] if x["id"] == appt["id"])
    assert row["price_amount"] == 250000


def test_appointment_with_inactive_service_blocked(client, manager_headers):
    """B06 در مسیر کارکنان: نوبت با خدمت غیرفعال رد می‌شود (ساخت مستقیم در DB)."""
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        sp = Specialty(name=f"فاز۲۸-غیرفعال-{uuid.uuid4().hex[:8]}")
        db.add(sp)
        db.flush()
        svc = Service(specialty_id=sp.id, title="خدمت غیرفعال مستقیم",
                      duration_minutes=30, status="inactive")
        db.add(svc)
        db.commit()
        svc_id = str(svc.id)
    finally:
        db.close()
    case_id = client.get("/api/v1/cases?page_size=1", headers=manager_headers).json()["items"][0]["id"]
    r = client.post("/api/v1/appointments", headers=manager_headers, json={
        "case_id": case_id, "service_id": svc_id,
        "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
    })
    assert r.status_code == 409
