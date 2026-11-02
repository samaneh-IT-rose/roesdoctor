"""فاز ۷۴ — تست منطق محور (بدون بانک) برای: رجیستری منو، fallback ماتریس،
ایزولاسیون سازمانی، و اعتبارسنجی روزهای مشاوره."""
import sys

sys.path.insert(0, ".")

import os

os.environ["DATABASE_URL"] = "postgresql+psycopg://rosepsy:change_me@localhost:5432/rosepsy"

from datetime import datetime

from app.core.menu_registry import MENU_KEYS, MENU_SEED, resolve_menu
from app.api.deps import menu_allows, _strip_api_prefix


class FakeRole:
    def __init__(self, code):
        self.code = code


class FakeUser:
    def __init__(self, codes, organization_id=None):
        self.roles = [FakeRole(c) for c in codes]
        self.organization_id = organization_id


class FakeDB:
    """db.scalars(...) → فیکِ رکوردهای ماتریس/دسترس‌پذیری"""

    def __init__(self, menu_rows=None, windows=None):
        self.menu_rows = menu_rows or []
        self.windows = windows or []

    class _R:
        def __init__(self, items):
            self._items = items

        def all(self):
            return self._items

        def first(self):
            return self._items[0] if self._items else None

    def scalars(self, *a, **k):
        return FakeDB._R(self.menu_rows + self.windows)


# ─── ۱) رجیستری: منوی جدید + resolve ───
assert "org-exam-results" in MENU_KEYS, "منوی جدید در رجیستری نیست"
r = resolve_menu("GET", "/org-exam-results")
assert r == ("org-exam-results", "view"), r
r = resolve_menu("GET", "/org-exam-results/0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0")
assert r == ("org-exam-results", "read"), r
r = resolve_menu("POST", "/org-exam-results")
assert r == ("org-exam-results", "edit"), r
seeds = {(role, key): level for role, key, level in MENU_SEED if key == "org-exam-results"}
assert set(seeds) == {
    ("ORG_MANAGER", "org-exam-results"),
    ("RECEPTION", "org-exam-results"),
    ("TECHNICAL_SUPERVISOR", "org-exam-results"),
    ("COUNSELOR", "org-exam-results"),
}, seeds
print("1) menu registry OK — org-exam-results + seeds")

# ─── ۲) fallback ماتریس در require_roles ───
# APPLICANT با مجوز ماتریس view روی org-programs باید مجاز شود
db = FakeDB(menu_rows=[type("R", (), {"menu_key": "org-programs", "level": "view"})()])
u = FakeUser(["APPLICANT"])
assert _strip_api_prefix("/api/v1/org-programs") == "/org-programs"
assert menu_allows(db, u, "GET", "/api/v1/org-programs") is True
# ولی ویرایش (POST) نه
assert menu_allows(db, u, "POST", "/api/v1/org-programs") is False
# بدون مجوز ماتریس: رد
db2 = FakeDB(menu_rows=[])
assert menu_allows(db2, u, "GET", "/api/v1/org-programs") is False
# COUNSELOR با read روی org-programs: GET فهرست بله، جزئیات (UUID) چون read≥read بله، POST نه
u3 = FakeUser(["COUNSELOR"])
db3 = FakeDB(menu_rows=[type("R", (), {"menu_key": "org-programs", "level": "read"})()])
assert menu_allows(db3, u3, "GET", "/api/v1/org-programs") is True
assert (
    menu_allows(db3, u3, "GET", "/api/v1/org-programs/0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0")
    is True
)
assert menu_allows(db3, u3, "POST", "/api/v1/org-programs") is False
print("2) require_roles matrix fallback OK")

# ─── ۳) اعتبارسنجی روزهای مشاوره ───
from app.api.v1.appointments import availability_conflict


def w(weekday, sh, eh, active=True):
    return type(
        "W", (), {"weekday": weekday, "start_time": sh, "end_time": eh, "is_active": active}
    )()


from datetime import time as dtime

# شنبه (weekday=5) ۹ تا ۱۲
db4 = FakeDB(windows=[w(5, dtime(9, 0), dtime(12, 0))])
# شنبه ۱۰:۰۰ — naive datetime → مجاز
ok = datetime(2026, 11, 7, 10, 0)  # 2026-11-07 شنبه است
assert availability_conflict(db4, "x", ok) is None, availability_conflict(db4, "x", ok)
# شنبه ۱۴:۰۰ — خارج بازه
bad = datetime(2026, 11, 7, 14, 0)
conf = availability_conflict(db4, "x", bad)
assert conf is not None and "شنبه" in conf, conf
# یکشنبه — روز اشتباه
bad2 = datetime(2026, 11, 8, 10, 0)
assert availability_conflict(db4, "x", bad2) is not None
# مشاور بدون تعریف بازه → بدون محدودیت
assert availability_conflict(FakeDB(), "x", bad) is None
print("3) counselor availability validation OK")

# ─── ۴) اسلات‌های booking از بازهٔ مشاور ───
from app.core.booking import _slot_starts, counselor_windows

from datetime import date

db5 = FakeDB(windows=[w(5, dtime(16, 0), dtime(19, 0))])
win = counselor_windows(db5, "c1")
assert win == {5: [(dtime(16, 0), dtime(19, 0))]}, win
slots = _slot_starts(date(2026, 11, 7), win)  # شنبه
labels = [s.strftime("%H:%M") for s in slots]
assert labels[0] == "16:00" and labels[-1] == "18:00", labels
# جمعه (weekday=4) با تعریف بازه توسط مشاور → اسلات دارد (قبلاً تعطیل بود)
db6 = FakeDB(windows=[w(4, dtime(9, 0), dtime(12, 0))])
win6 = counselor_windows(db6, "c2")
assert len(_slot_starts(date(2026, 11, 6), win6)) == 3
# بدون تعریف → رفتار قبلی (جمعه تعطیل)
assert _slot_starts(date(2026, 11, 6), None) == []
print("4) booking counselor-aware slots OK")

print("\nALL PHASE-74 LOGIC TESTS PASSED")
