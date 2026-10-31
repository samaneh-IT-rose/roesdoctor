"""فاز ۶۹ - رزرو آنلاین با پرداخت درگاه (زرین‌پال/شبیه‌ساز) + امتیازدهی مشاوران.

- submit با pay_online=true → رزرو + سفارش + پرداخت initiated (درگاه sandbox
  وقتی زرین‌پال پیکربندی نشده) و اسلات تا سقف TTL اشغال می‌ماند.
- callback GET (بازگشت مرورگر از درگاه) → تأیید قطعی + رزرو paid + توکن نظر
  + ریدایرکت به صفحهٔ نتیجهٔ سایت.
- نظر فقط با توکن رزرو پرداخت‌شده؛ یک نظر برای هر رزرو؛ امتیاز ۱..۵.
- فهرست عمومی مشاوران بر اساس امتیاز (بالاترین اول) مرتب می‌شود.
- رزرو پرداخت‌نشدهٔ منقضی (TTL) اسلات را آزاد می‌کند.
"""
from datetime import date, datetime, timedelta, timezone

import pytest

from conftest import login


@pytest.fixture()
def _no_rate_limit():
    """پاک‌سازی محدودساز نرخ درون‌حافظه‌ای endpoints عمومی."""
    from app.api.v1 import public as public_mod

    public_mod._req_ip.clear()
    public_mod._hold_ip.clear()
    yield
    public_mod._req_ip.clear()
    public_mod._hold_ip.clear()


def _mk_service(client) -> dict:
    import uuid as _uuid

    m = {"Authorization": f"Bearer {login(client, 't_manager')}"}
    r = client.post("/api/v1/specialties", headers=m, json={"name": f"فاز۶۹-{_uuid.uuid4().hex[:8]}"})
    sp = r.json()
    r = client.post("/api/v1/services", headers=m, json={
        "specialty_id": sp["id"], "title": "خدمت فاز۶۹", "duration_minutes": 45,
    })
    assert r.status_code == 201, r.text
    svc = r.json()
    on = date.today() - timedelta(days=1)
    r = client.post("/api/v1/tariffs", headers=m, json={
        "service_id": svc["id"], "amount": 900000,
        "valid_from": str(on), "valid_to": str(on + timedelta(days=101)),
    })
    assert r.status_code == 201, r.text
    return svc


def _free_slot(client, env) -> str:
    r = client.get(f"/api/v1/public/booking/slots?counselor_id={str(env['counselor_b'].id)}")
    assert r.status_code == 200, r.text
    days = r.json()["days"]
    assert days, "هیچ اسلات آزادی یافت نشد"
    return days[0]["slots"][0]["start_at"]


def _book_paid(client, env, svc, pay_online=True):
    """hold + submit (با/بدون پرداخت آنلاین) → dict پاسخ."""
    start = _free_slot(client, env)
    r = client.post("/api/v1/public/booking-holds", json={
        "counselor_id": str(env["counselor_b"].id), "start_at": start,
    })
    assert r.status_code == 201, r.text
    hold = r.json()
    r = client.post("/api/v1/public/consultation-requests", json={
        "full_name": "کاربر آزمون فاز۶۹",
        "mobile": "09121234069",
        "topic": "مشاوره فردی",
        "counselor_id": str(env["counselor_b"].id),
        "start_at": start,
        "hold_token": hold["hold_token"],
        "service_id": svc["id"],
        "pay_online": pay_online,
    })
    assert r.status_code == 201, r.text
    return r.json(), start


def test_paid_booking_creates_order_payment_and_blocks_slot(client, env, _no_rate_limit):
    svc = _mk_service(client)
    resp, start = _book_paid(client, env, svc)
    assert resp["status"] == "ok"
    pay = resp["payment"]
    assert pay["gateway"] == "sandbox"  # زرین‌پال پیکربندی نشده → شبیه‌ساز
    assert pay["redirect_url"].startswith("/api/v1/sandbox-gateway?authority=")
    assert pay["amount"] == 900000

    # رزرو در انتظار پرداخت → اسلات اشغال (از فهرست آزاد خارج شده است)
    r = client.get(f"/api/v1/public/booking/slots?counselor_id={str(env['counselor_b'].id)}")
    all_slots = [s for d in r.json()["days"] for s in d["slots"]]
    assert all(s["start_at"] != start for s in all_slots)

    # سفارش با اتصال به رزرو ساخته شده است
    r2 = client.get("/api/v1/orders", headers={
        "Authorization": f"Bearer {login(client, 't_manager')}"})
    assert r2.status_code == 200


def test_get_callback_marks_paid_and_issues_review_token(client, env, _no_rate_limit):
    svc = _mk_service(client)
    resp, start = _book_paid(client, env, svc)
    authority = resp["payment"]["authority"]
    request_id = resp["request_id"]

    # بازگشت مرورگر از درگاه: GET با status=OK
    r = client.get(
        f"/api/v1/payments/callback/sandbox?authority={authority}&status=OK",
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text
    loc = r.headers["location"]
    assert "state=success" in loc and f"req={request_id}" in loc and "token=" in loc

    # رزرو حالا پرداخت‌شده است و اسلات می‌ماند (پرداخت‌شده همیشه اشغال)
    r = client.get(f"/api/v1/public/booking/slots?counselor_id={str(env['counselor_b'].id)}")
    all_slots = [s for d in r.json()["days"] for s in d["slots"]]
    assert all(s["start_at"] != start for s in all_slots)

    # callback تکراری بی‌اثر (idempotent) - باز هم success
    r2 = client.get(
        f"/api/v1/payments/callback/sandbox?authority={authority}&status=OK",
        follow_redirects=False,
    )
    assert r2.status_code == 303 and "state=success" in r2.headers["location"]

    # توکن از URL
    token = loc.split("token=")[1].split("&")[0]
    cid = str(env["counselor_b"].id)
    r = client.post(f"/api/v1/public/counselors/{cid}/reviews", json={
        "review_token": token, "rating": 5, "comment": "بسیار عالی و حرفه‌ای",
    })
    assert r.status_code == 201, r.text

    # نظر دوم برای همان رزرو → ۴۰۹
    r = client.post(f"/api/v1/public/counselors/{cid}/reviews", json={
        "review_token": token, "rating": 4,
    })
    assert r.status_code == 409

    # امتیاز ۶ → ۴۲۲
    resp2, _ = _book_paid(client, env, svc)
    tok2 = None
    a2 = resp2["payment"]["authority"]
    r = client.get(f"/api/v1/payments/callback/sandbox?authority={a2}&status=OK",
                   follow_redirects=False)
    tok2 = r.headers["location"].split("token=")[1].split("&")[0]
    r = client.post(f"/api/v1/public/counselors/{cid}/reviews", json={
        "review_token": tok2, "rating": 6,
    })
    assert r.status_code == 422

    # فهرست نظرات عمومی + خلاصه (فقط نظر اول ثبت شده؛ امتیاز ۶ رد شده است)
    r = client.get(f"/api/v1/public/counselors/{cid}/reviews")
    data = r.json()
    assert data["summary"]["review_count"] == 1
    assert data["summary"]["rating_avg"] == 5.0
    assert data["items"][0]["author"].startswith("کاربر")


def test_review_requires_valid_paid_token(client, env, _no_rate_limit):
    svc = _mk_service(client)
    cid = str(env["counselor_b"].id)
    # توکن نامعتبر
    r = client.post(f"/api/v1/public/counselors/{cid}/reviews", json={
        "review_token": "x" * 32, "rating": 5,
    })
    assert r.status_code == 403

    # رزرو بدون پرداخت آنلاین → توکن ندارد؛ ثبت نظر با توکن رزروی دیگر که پرداخت نشده
    resp, _ = _book_paid(client, env, svc, pay_online=False)
    request_id = resp["request_id"]
    r = client.post(f"/api/v1/public/counselors/{cid}/reviews", json={
        "review_token": request_id.replace("-", "")[:32], "rating": 5,
    })
    assert r.status_code == 403

    # توکن مشاور اشتباه: پرداخت رزرو مشاور B ولی امتیاز به مشاور A
    resp2, _ = _book_paid(client, env, svc)
    a2 = resp2["payment"]["authority"]
    r = client.get(f"/api/v1/payments/callback/sandbox?authority={a2}&status=OK",
                   follow_redirects=False)
    tok = r.headers["location"].split("token=")[1].split("&")[0]
    r = client.post(f"/api/v1/public/counselors/{str(env['counselor_a'].id)}/reviews", json={
        "review_token": tok, "rating": 5,
    })
    assert r.status_code == 403


def test_rating_sort_in_public_listings(client, env, _no_rate_limit):
    svc = _mk_service(client)
    cid_b = str(env["counselor_b"].id)
    cid_a = str(env["counselor_a"].id)
    # دو نظر ۵ ستاره برای مشاور B
    for _ in range(2):
        resp, _ = _book_paid(client, env, svc)
        a = resp["payment"]["authority"]
        r = client.get(f"/api/v1/payments/callback/sandbox?authority={a}&status=OK",
                       follow_redirects=False)
        tok = r.headers["location"].split("token=")[1].split("&")[0]
        r = client.post(f"/api/v1/public/counselors/{cid_b}/reviews", json={
            "review_token": tok, "rating": 5,
        })
        assert r.status_code == 201

    r = client.get("/api/v1/public/counselors")
    items = r.json()["items"]
    ids = [x["id"] for x in items]
    assert ids.index(cid_b) < ids.index(cid_a), "مشاور با امتیاز بالاتر باید اول باشد"
    b_item = next(x for x in items if x["id"] == cid_b)
    assert b_item["rating_avg"] == 5.0 and b_item["review_count"] >= 2
    a_item = next(x for x in items if x["id"] == cid_a)
    assert a_item["rating_avg"] is None and a_item["review_count"] == 0


def test_nok_callback_marks_failed_and_frees_slot(client, env, _no_rate_limit):
    svc = _mk_service(client)
    resp, start = _book_paid(client, env, svc)
    authority = resp["payment"]["authority"]
    r = client.get(f"/api/v1/payments/callback/sandbox?authority={authority}&status=NOK",
                   follow_redirects=False)
    assert r.status_code == 303
    assert "state=failed" in r.headers["location"]
    # رزرو ناموفق → اسلات آزاد می‌شود (پرداخت ناموفق بلافاصله غیراشغال)
    r = client.get(f"/api/v1/public/booking/slots?counselor_id={str(env['counselor_b'].id)}")
    all_slots = [s for d in r.json()["days"] for s in d["slots"]]
    assert any(s["start_at"] == start for s in all_slots)


def test_stale_unpaid_request_releases_slot(client, env, _no_rate_limit):
    """رزرو pending که ۳ ساعت ماند و پرداخت نشد → اسلات آزاد (TTL=۲ ساعت)."""
    from app.db.session import SessionLocal
    from app.models.consultation import ConsultationRequest

    svc = _mk_service(client)
    resp, start = _book_paid(client, env, svc)
    request_id = resp["request_id"]

    db = SessionLocal()
    try:
        cr = db.get(ConsultationRequest, __import__("uuid").UUID(request_id))
        cr.created_at = datetime.now(timezone.utc) - timedelta(hours=3)
        db.commit()
    finally:
        db.close()

    r = client.get(f"/api/v1/public/booking/slots?counselor_id={str(env['counselor_b'].id)}")
    all_slots = [s for d in r.json()["days"] for s in d["slots"]]
    assert any(s["start_at"] == start for s in all_slots)

    # فاز ۶۹: اسلات آزادشده باید واقعاً قابل رزرو مجدد باشد (ایندکس یکتا آزاد شود)
    r = client.post("/api/v1/public/booking-holds", json={
        "counselor_id": str(env["counselor_b"].id), "start_at": start})
    assert r.status_code == 201, r.text
    hold2 = r.json()
    r = client.post("/api/v1/public/consultation-requests", json={
        "full_name": "کاربر بعدی", "mobile": "09121234068", "topic": "مشاوره فردی",
        "counselor_id": str(env["counselor_b"].id), "start_at": start,
        "hold_token": hold2["hold_token"], "service_id": svc["id"], "pay_online": True})
    assert r.status_code == 201, r.text
    assert "payment" in r.json()


def test_legacy_booking_flow_unchanged(client, env, _no_rate_limit):
    """جریان قدیمی (بدون pay_online) دست‌نخورده: payment_status='not_required' و بدون سفارش."""
    from app.db.session import SessionLocal
    from app.models.consultation import ConsultPaymentStatus, ConsultationRequest
    import uuid as _uuid

    svc = _mk_service(client)
    resp, _ = _book_paid(client, env, svc, pay_online=False)
    assert "payment" not in resp and "payment_error" not in resp
    db = SessionLocal()
    try:
        cr = db.get(ConsultationRequest, _uuid.UUID(resp["request_id"]))
        assert cr.payment_status == ConsultPaymentStatus.NOT_REQUIRED
    finally:
        db.close()


def test_pay_online_requires_service_and_tariff(client, env, _no_rate_limit):
    """پرداخت آنلاین بدون خدمت → ۴۲۲."""
    start = _free_slot(client, env)
    r = client.post("/api/v1/public/booking-holds", json={
        "counselor_id": str(env["counselor_b"].id), "start_at": start,
    })
    hold = r.json()
    r = client.post("/api/v1/public/consultation-requests", json={
        "full_name": "کاربر بدون خدمت", "mobile": "09121234070",
        "topic": "مشاوره فردی", "counselor_id": str(env["counselor_b"].id),
        "start_at": start, "hold_token": hold["hold_token"], "pay_online": True,
    })
    assert r.status_code == 422
