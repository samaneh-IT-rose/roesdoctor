"""فاز ۷۱ — رجیستری مرکزی منوها و زیرمنوهای پنل + ماتریس دسترسی سه‌سطحی.

این ماژول «تک منبع حقیقت» نقشهٔ منوی پنل است:
- هر زیرمنو یک ``key`` پایدار دارد که هم فرانت (Layout.tsx) و هم ماتریس
  «نقش‌ها و دسترسی‌ها» از همان استفاده می‌کنند؛
- سطح دسترسی هر منو برای هر نقش در جدول ``role_menu_permissions`` نگه داشته
  می‌شود و سه سطح مثبت دارد:

    view  (دیدن)   → منو دیده می‌شود؛ فهرست/صفحهٔ اصلی بخش باز می‌شود
    read  (خواندن) → جزئیات رکوردها هم قابل مشاهده است (تغییری نمی‌تواند بدهد)
    edit  (ویرایش) → ثبت/ویرایش/حذف در آن بخش (شامل سطح‌های پایین‌تر)

  نبودِ ردیف یعنی «هیچ» — منو پنهان و تمام مسیرهای API آن بخش مسدود است.
- این ماژول عمداً هیچ وابستگی به app ندارد (فقط stdlib) تا هم در مایگریشن
  آلمبیک و هم در خودترمیم استارتاپ بدون خطر import دورهاستفاده شود.
"""
from __future__ import annotations

import re

# سطوح دسترسی منو (ترتیب = ارتقاع) — «هیچ» یعنی نبودِ ردیف
MENU_LEVELS: tuple[str, ...] = ("view", "read", "edit")
LEVEL_RANK: dict[str, int] = {"view": 1, "read": 2, "edit": 3}

LEVEL_TITLES: dict[str, str] = {
    "view": "دیدن",
    "read": "فقط خواندن",
    "edit": "ویرایش",
}

# segment UUID (همهٔ شناسه‌های موجودیت این سامانه UUID هستند)
_UUID_SEG = re.compile(
    r"/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}(?:/|$)"
)

# متدهای تغییردهنده → سطح «ویرایش»
_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class MenuEntry(dict):
    """یک زیرمنو: key پایدار + عنوان + مسیر پنل + نگاشت مسیرهای API.

    - ``self_service=True`` → داده‌های شخصی خود کاربر است (کیف پول، چت، …)؛
      ماتریس فقط «نمایش منو» را کنترل می‌کند و مسیرهای API آن دروازه‌بانی
      نمی‌شود (جداسازی داده با مالکیت رکورد تضمین شده است).
    - ``prefixes`` → مسیرهای API (بدون /api/v1) که به این منو تعلق دارند؛
      فقط برای منوهای غیر self_service اعمال می‌شود.
    - ``public_prefixes`` → زیرمسیرهای عمومی/خرید که هرگز دروازه‌بانی نمی‌شوند.
    - ``pattern`` → قاعدهٔ ویژهٔ تطبیق (مثل پاسخ‌های فرم) با بیشترین اولویت.
    """

    @property
    def key(self) -> str:
        return self["key"]

    @property
    def self_service(self) -> bool:
        return bool(self.get("self_service"))


MENU_GROUPS: list[dict] = [
    {
        "key": "workdesk",
        "title": "میز کار",
        "items": [
            MenuEntry(key="dashboard", title="داشبورد عملیاتی", path="/dashboard",
                      prefixes=["/reports/summary"]),
            MenuEntry(key="cartable", title="کارتابل من", path="/cartable", self_service=True),
            MenuEntry(key="admin-dashboard", title="داشبورد مدیر", path="/admin-dashboard",
                      prefixes=["/reports/admin-dashboard"]),
            MenuEntry(key="dpo-report", title="گزارش انطباق DPO", path="/dpo-report",
                      prefixes=["/compliance"]),
            MenuEntry(key="chat", title="گفتگوی آنلاین", path="/chat", self_service=True),
            MenuEntry(key="my-forms", title="فرم‌های من (نظرسنجی‌ها)", path="/my-forms",
                      self_service=True),
        ],
    },
    {
        "key": "cases-group",
        "title": "پرونده و درمان",
        "items": [
            MenuEntry(key="cases", title="پرونده‌ها", path="/cases",
                      prefixes=["/cases", "/assessments", "/sessions", "/referrals"]),
            MenuEntry(key="consultation-requests", title="درخواست‌های مشاوره",
                      path="/consultation-requests", prefixes=["/consultation-requests"]),
            MenuEntry(key="worklist", title="کارتابل مشاور", path="/worklist",
                      prefixes=["/worklists/counselor", "/worklists/counselor-appointments"]),
            MenuEntry(key="my-assessments", title="ارزیابی‌های من", path="/my-assessments",
                      self_service=True),
            MenuEntry(key="reviews", title="بررسی‌های فنی", path="/reviews",
                      prefixes=["/worklists/supervisor"]),
            MenuEntry(key="level3-alerts", title="هشدارهای سطح ۳", path="/level3-alerts",
                      prefixes=["/worklists/level3"]),
            MenuEntry(key="supervised-cases", title="پرونده‌های تحت نظارت",
                      path="/supervised-cases", prefixes=["/worklists/supervised-cases"]),
        ],
    },
    {
        "key": "intake",
        "title": "پذیرش و مشتریان",
        "items": [
            MenuEntry(key="applicants", title="متقاضیان", path="/applicants",
                      prefixes=["/applicants"]),
            MenuEntry(key="public-chats", title="گفتگوهای عمومی سایت", path="/public-chats",
                      prefixes=["/public-chat/admin"]),
            MenuEntry(key="imports", title="ورود اکسل", path="/imports",
                      prefixes=["/imports"]),
        ],
    },
    {
        "key": "content",
        "title": "محتوا و آموزش",
        "items": [
            MenuEntry(key="topics", title="دسته‌بندی موضوعی", path="/topics",
                      prefixes=["/topics"], public_prefixes=["/topics/public"]),
            MenuEntry(key="learning", title="محتوا و دوره‌ها", path="/learning",
                      prefixes=["/learning"]),
            MenuEntry(key="psych-tests", title="مرکز آزمون روان‌شناسی", path="/psych-tests",
                      self_service=True),
            MenuEntry(key="psych-attempts", title="آزمون‌های برگزارشده", path="/psych-attempts",
                      prefixes=["/psych-attempts"]),
            MenuEntry(key="counseling-files", title="پرونده‌های مشاوره", path="/counseling-files",
                      prefixes=["/counseling-files"]),
        ],
    },
    {
        "key": "finance",
        "title": "مالی",
        "items": [
            # سفارش/پرداخت مسیر مشترک خرید همهٔ کاربران است → فقط کنترل نمایش منو
            MenuEntry(key="orders", title="سفارش و پرداخت", path="/orders", self_service=True),
            MenuEntry(key="wallet", title="کیف پول", path="/wallet", self_service=True),
            MenuEntry(key="accounting", title="حسابداری", path="/accounting",
                      prefixes=["/accounting"]),
            MenuEntry(key="services", title="خدمات و تعرفه‌ها", path="/services",
                      prefixes=["/services", "/tariffs", "/specialties"]),
        ],
    },
    {
        "key": "org",
        "title": "سازمان و منابع",
        "items": [
            MenuEntry(key="organizations", title="سازمان‌ها", path="/organizations",
                      prefixes=["/organizations", "/contracts", "/statements"]),
            MenuEntry(key="org-programs", title="آزمون‌های سازمانی", path="/org-programs",
                      prefixes=["/org-programs"]),
            MenuEntry(key="counselors", title="مشاوران", path="/counselors",
                      prefixes=["/counselors"]),
            MenuEntry(key="verification-reviews", title="بازبینی صلاحیت",
                      path="/verification-reviews", prefixes=["/verification-reviews"]),
            MenuEntry(key="branches", title="شعب", path="/branches",
                      prefixes=["/clinics", "/branches"]),
        ],
    },
    {
        "key": "system",
        "title": "سامانه و پشتیبانی",
        "items": [
            MenuEntry(key="processes", title="فرایندها (BPMN)", path="/processes",
                      prefixes=["/processes"]),
            MenuEntry(key="process-monitoring", title="مانیتورینگ فرایندها",
                      path="/process-monitoring", prefixes=["/process-instances"]),
            MenuEntry(key="form-builder", title="فرم‌ساز و نظرسنجی", path="/form-builder",
                      prefixes=["/form-templates/admin"]),
            MenuEntry(key="form-responses", title="پاسخ‌های فرم‌ها", path="/form-responses",
                      prefixes=["/form-templates/admin"],
                      pattern=r"^/form-templates/admin/[^/]+/responses"),
            MenuEntry(key="support", title="پشتیبانی", path="/support", self_service=True),
            MenuEntry(key="assistant", title="دستیار هوشمند", path="/assistant",
                      self_service=True),
            MenuEntry(key="integrations", title="یکپارچه‌سازی‌ها", path="/integrations",
                      prefixes=["/integrations", "/sms-outbox"]),
            MenuEntry(key="users", title="کاربران", path="/users", prefixes=["/users"]),
            MenuEntry(key="roles-permissions", title="نقش‌ها و دسترسی‌ها",
                      path="/roles-permissions", prefixes=["/rbac"],
                      public_prefixes=["/rbac/me/permissions"]),
            MenuEntry(key="audit-events", title="رخدادهای امنیتی", path="/audit-events",
                      prefixes=["/audit-events"]),
        ],
    },
]

# لینک‌های ایستا (راهنما/گزارش پیشرفت) جزو ماتریس نیستند — برای همه دیده می‌شوند

ALL_MENU_ENTRIES: list[MenuEntry] = [
    item for group in MENU_GROUPS for item in group["items"]
]

MENU_KEYS: tuple[str, ...] = tuple(e["key"] for e in ALL_MENU_ENTRIES)

_MENU_BY_KEY: dict[str, MenuEntry] = {e["key"]: e for e in ALL_MENU_ENTRIES}


def menu_title(key: str) -> str:
    entry = _MENU_BY_KEY.get(key)
    return (entry["title"] if entry else key)


def is_menu_key(key: str) -> bool:
    return key in _MENU_BY_KEY


def required_level(method: str, path: str) -> str:
    """سطح لازم برای یک فراخوانی API:
    - متد تغییردهنده → ویرایش؛
    - GET/HEAD با آیدی UUID در مسیر (جزئیات رکورد) → خواندن؛
    - بقیهٔ GET (فهرست/آمار/گزارش) → دیدن.
    """
    if method.upper() in _MUTATING_METHODS:
        return "edit"
    if _UUID_SEG.search(path):
        return "read"
    return "view"


# رجیستری مرتب‌شده برای تطبیق مسیر: الگوها اول، بعد طولانی‌ترین پیشوند
_MATCH_RULES: list[tuple[str, MenuEntry]] = []


def _build_match_rules() -> None:
    rules: list[tuple[int, str, MenuEntry]] = []
    for entry in ALL_MENU_ENTRIES:
        if entry.self_service:
            continue
        pat = entry.get("pattern")
        if pat:
            rules.append((10_000, pat, entry))
        for prefix in entry.get("prefixes", []):
            rules.append((len(prefix), "^" + re.escape(prefix) + r"(?:/|$)", entry))
    rules.sort(key=lambda r: r[0], reverse=True)
    _MATCH_RULES.clear()
    _MATCH_RULES.extend(
        (compiled, (entry, weight >= 10_000)) for weight, compiled, entry in
        ((w, re.compile(p), e) for w, p, e in rules)
    )


_build_match_rules()


def resolve_menu(method: str, path: str) -> tuple[str, str] | None:
    """(menu_key, سطح_لازم) برای مسیر API — بدون تطبیق یعنی None (بدون گیت)."""
    matched: MenuEntry | None = None
    via_pattern = False
    for rx, (entry, is_pattern) in _MATCH_RULES:
        if rx.search(path):
            matched = entry
            via_pattern = is_pattern
            break
    if matched is None:
        return None
    for pub in matched.get("public_prefixes", []):
        if path == pub or path.startswith(pub + "/"):
            return None
    if via_pattern:
        # قاعدهٔ ویژه (پاسخ‌های فرم): خودِ فهرست پاسخ‌ها هدفِ صفحه است → GET=دیدن
        return matched["key"], "edit" if method.upper() in _MUTATING_METHODS else "view"
    return matched["key"], required_level(method, path)


# ---------------------------------------------------------------------------
# نگاشت پیش‌فرض نقش‌های سیستمی — دقیقاً وضعیتِ فعلی منوها را بازتولید می‌کند
# (هیچ‌کس بعد از استقرار منویی را از دست نمی‌دهد) و مدیر از همین نقطه می‌تواند
# برای هر نقش هر منو را به «دیدن / خواندن / ویرایش» تغییر دهد.
# SYSTEM_ADMIN عمداً ردیفی ندارد — همیشه دسترسی کامل دارد (bypass).
# ---------------------------------------------------------------------------
ALL_STAFF = ("ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR")
SELF_ROLES = ("ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR", "APPLICANT", "DPO")


def _seed(role: str, key: str, level: str) -> tuple[str, str, str]:
    return (role, key, level)


MENU_SEED: list[tuple[str, str, str]] = [
    # ── میز کار ──
    *(_seed(r, "dashboard", "view") for r in ALL_STAFF),
    *(_seed(r, "cartable", "edit") for r in ALL_STAFF),
    _seed("ORG_MANAGER", "admin-dashboard", "edit"),
    _seed("ORG_MANAGER", "dpo-report", "read"),
    _seed("DPO", "dpo-report", "read"),
    *(_seed(r, "chat", "edit") for r in SELF_ROLES),
    *(_seed(r, "my-forms", "edit") for r in SELF_ROLES),
    # ── پرونده و درمان ──
    *(_seed(r, "cases", "edit") for r in ALL_STAFF),
    _seed("ORG_MANAGER", "consultation-requests", "edit"),
    _seed("RECEPTION", "consultation-requests", "edit"),
    _seed("COUNSELOR", "consultation-requests", "read"),
    # فاز ۷۱: مسئول فنی پذیرش/فرم اولیه را می‌خواند (رفتار قبلی)
    _seed("TECHNICAL_SUPERVISOR", "consultation-requests", "read"),
    _seed("COUNSELOR", "worklist", "edit"),
    _seed("COUNSELOR", "my-assessments", "edit"),
    _seed("TECHNICAL_SUPERVISOR", "reviews", "edit"),
    _seed("TECHNICAL_SUPERVISOR", "level3-alerts", "edit"),
    _seed("TECHNICAL_SUPERVISOR", "supervised-cases", "edit"),
    # ── پذیرش و مشتریان ──
    _seed("ORG_MANAGER", "applicants", "edit"),
    _seed("RECEPTION", "applicants", "edit"),
    _seed("ORG_MANAGER", "public-chats", "read"),
    _seed("RECEPTION", "public-chats", "read"),
    _seed("ORG_MANAGER", "imports", "edit"),
    _seed("RECEPTION", "imports", "edit"),
    # ── محتوا و آموزش ──
    _seed("ORG_MANAGER", "topics", "edit"),
    _seed("RECEPTION", "topics", "edit"),
    _seed("COUNSELOR", "topics", "edit"),
    _seed("TECHNICAL_SUPERVISOR", "topics", "read"),
    _seed("ORG_MANAGER", "learning", "edit"),
    _seed("TECHNICAL_SUPERVISOR", "learning", "edit"),
    _seed("RECEPTION", "learning", "read"),
    _seed("COUNSELOR", "learning", "read"),
    *(_seed(r, "psych-tests", "edit") for r in (*ALL_STAFF, "APPLICANT")),
    # فاز ۷۱ — جداسازی آزمون: متقاضی فهرست «آزمون‌های برگزارشده» را می‌بیند ولی
    # سمت سرور فقط آزمون‌های خودش را برمی‌گرداند (هر کاربر فقط آزمون خودش)
    _seed("APPLICANT", "psych-attempts", "view"),
    _seed("ORG_MANAGER", "psych-attempts", "edit"),
    _seed("RECEPTION", "psych-attempts", "edit"),
    _seed("TECHNICAL_SUPERVISOR", "psych-attempts", "read"),
    _seed("COUNSELOR", "psych-attempts", "read"),
    _seed("ORG_MANAGER", "counseling-files", "edit"),
    _seed("RECEPTION", "counseling-files", "edit"),
    _seed("TECHNICAL_SUPERVISOR", "counseling-files", "read"),
    _seed("COUNSELOR", "counseling-files", "read"),
    # ── مالی ──
    _seed("ORG_MANAGER", "orders", "edit"),
    _seed("RECEPTION", "orders", "edit"),
    *(_seed(r, "wallet", "edit") for r in SELF_ROLES),
    _seed("ORG_MANAGER", "accounting", "edit"),
    _seed("ORG_MANAGER", "services", "edit"),
    *(_seed(r, "services", "read") for r in ("RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR")),
    # ── سازمان و منابع ──
    _seed("ORG_MANAGER", "organizations", "edit"),
    *(_seed(r, "organizations", "read") for r in ("RECEPTION", "TECHNICAL_SUPERVISOR")),
    _seed("ORG_MANAGER", "org-programs", "edit"),
    *(_seed(r, "org-programs", "read") for r in ("RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR")),
    _seed("ORG_MANAGER", "counselors", "edit"),
    _seed("TECHNICAL_SUPERVISOR", "counselors", "edit"),
    _seed("ORG_MANAGER", "verification-reviews", "edit"),
    _seed("TECHNICAL_SUPERVISOR", "verification-reviews", "edit"),
    _seed("ORG_MANAGER", "branches", "edit"),
    *(_seed(r, "branches", "read") for r in ("RECEPTION", "TECHNICAL_SUPERVISOR")),
    # ── سامانه و پشتیبانی ──
    # فرایندها: مدیر سازمان فرایند/نسخه می‌سازد (MANAGE_ROLES)؛ بقیه فقط می‌بینند
    _seed("ORG_MANAGER", "processes", "edit"),
    *(_seed(r, "processes", "read") for r in ("RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR")),
    # مانیتورینگ: پذیرش/مشاور نمونهٔ فرایند را شروع و گام ثبت می‌کنند (رفتار قبلی)
    *(_seed(r, "process-monitoring", "edit") for r in ALL_STAFF),
    _seed("ORG_MANAGER", "form-builder", "edit"),
    _seed("ORG_MANAGER", "form-responses", "edit"),
    *(_seed(r, "support", "edit") for r in (*SELF_ROLES, "DPO")),
    *(_seed(r, "assistant", "edit") for r in (*SELF_ROLES, "DPO")),
    _seed("ORG_MANAGER", "integrations", "edit"),
    # رخدادهای امنیتی: مدیر سازمان (گزارش DPO صفحه audit-events می‌خواند) و DPO
    _seed("ORG_MANAGER", "audit-events", "read"),
    _seed("DPO", "audit-events", "read"),
    # users / roles-permissions فقط SYSTEM_ADMIN → بدون ردیف
]
