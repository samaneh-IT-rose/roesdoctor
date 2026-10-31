from fastapi import FastAPI

from app.core.deprecation import V1DeprecationMiddleware
from app.core.envelope import API_V2_PREFIX, EnvelopeMiddleware
from app.core.guards import NullByteGuardMiddleware
from app.core.idempotency import FinancialIdempotencyMiddleware
from app.core.rate_limit import RateLimitMiddleware

from app.api.v1.ai import router as ai_router
from app.api.v1.applicants import router as applicants_router
from app.api.v1.appointments import router as appointments_router
from app.api.v1.assessments import router as assessments_router
from app.api.v1.accounting import router as accounting_router
from app.api.v1.auth import router as auth_router
from app.api.v1.rose_sso import router as rose_sso_router
from app.api.v1.branches import router as branches_router
from app.api.v1.cartable import router as cartable_router
from app.api.v1.cases import router as cases_router
from app.api.v1.catalog import router as catalog_router
from app.api.v1.chat import router as chat_router
from app.api.v1.calls import router as calls_router
from app.api.v1.forms import router as forms_router
from app.api.v1.rbac import router as rbac_router
from app.api.v1.consents import router as consents_router
from app.api.v1.files import router as files_router
from app.api.v1.counselors import router as counselors_router
from app.api.v1.clinical import router as clinical_router
from app.api.v1.compliance import router as compliance_router
from app.api.v1.discounts import router as discounts_router
from app.api.v1.email_outbox import router as email_outbox_router
from app.api.v1.health import router as health_router
from app.api.v1.idempotency import router as idempotency_router
from app.api.v1.intake import router as intake_router
from app.api.v1.imports import router as imports_router
from app.api.v1.integrations import router as integrations_router
from app.api.v1.processes import router as processes_router
from app.api.v1.learning import router as learning_router
from app.api.v1.me import router as me_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.org import router as org_router
from app.api.v1.organizations import router as organizations_router
from app.api.v1.org_programs import router as org_programs_router
from app.api.v1.payments import router as payments_router
from app.api.v1.provinces import router as provinces_router
from app.api.v1.public import router as public_router
from app.api.v1.public_chat import router as public_chat_router
from app.api.v1.public_chat_admin import router as public_chat_admin_router
from app.api.v1.psych_tests import router as psych_tests_router
from app.api.v1.counseling import router as counseling_router
from app.api.v1.recommendations import router as recommendations_router
from app.api.v1.referrals import router as referrals_router
from app.api.v1.refunds import router as refunds_router
from app.api.v1.reports import router as reports_router
from app.api.v1.sessions import router as sessions_router
from app.api.v1.staff_site import router as staff_site_router
from app.api.v1.support import router as support_router
from app.api.v1.supervisor import router as supervisor_router
from app.api.v1.topics import router as topics_router
from app.api.v1.users import router as users_router
from app.api.v1.verification import router as verification_router
from app.api.v1.wallet import router as wallet_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=f"{settings.app_name} API",
    version=settings.app_version,
    docs_url=f"{settings.api_prefix}/docs",
    openapi_url=f"{settings.api_prefix}/openapi.json",
)

# فاز ۳۸ - ADR-03: همین روت‌ها دو بار سوار می‌شوند — v1 (قرارداد فعلی،
# سازگاری کامل فرانت/موبایل) و v2 (همان مسیرها با پاکت استاندارد
# {data, meta, errors}؛ خارج از OpenAPI تا طرح مستندات تمیز بماند).
_ROUTERS: list[tuple[object, list[str] | None]] = [
    (health_router, ["health"]),
    (idempotency_router, None),
    (auth_router, None),
    (accounting_router, None),
    (users_router, None),
    (org_router, None),
    (topics_router, None),
    (organizations_router, None),
    (org_programs_router, None),
    (counselors_router, None),
    (applicants_router, None),
    (imports_router, None),
    (cases_router, None),
    (assessments_router, None),
    (notifications_router, None),
    (consents_router, None),
    (files_router, None),
    (appointments_router, None),
    (sessions_router, None),
    (recommendations_router, None),
    (me_router, None),
    (supervisor_router, None),
    (reports_router, None),
    (clinical_router, None),
    (intake_router, None),
    (referrals_router, None),
    (public_router, None),
    # ورود یکپارچه (SSO) با رز هاب
    (rose_sso_router, None),
    (public_chat_router, ["public-chat"]),
    # فاز ۵۵: پنل پذیرش/مدیر — مشاهدهٔ گفتگوهای عمومی و امتیازها
    (public_chat_admin_router, ["public-chat-admin"]),
    (staff_site_router, None),
    (compliance_router, None),
    (email_outbox_router, None),
    (catalog_router, None),
    (verification_router, None),
    (branches_router, None),
    # فاز ۵۹: کارتابل شخصی هر حساب + نمای مدیریتی سطح دسترسی
    (cartable_router, None),
    (payments_router, None),
    (wallet_router, None),
    (discounts_router, None),
    (refunds_router, None),
    (learning_router, None),
    (support_router, None),
    (provinces_router, None),
    (psych_tests_router, None),
    # فاز ۷۰: پروندهٔ مشاورهٔ کاربر + تاریخچهٔ آزمون‌ها و مشاوره‌ها
    (counseling_router, None),
    (ai_router, None),
    (integrations_router, None),
    (processes_router, None),
    # فاز ۵۲: RBAC گرافیکی + چت آنلاین — WebSocket (chat/ws) فقط یک‌بار سوار
    # می‌شود؛ در حلقهٔ دوباره‌سواری v2 exclude نمی‌شویم چون include_router با
    # websocket route هم سازگار است، ولی برای جلوگیری از دو مسیر ws، چت را با
    # tags صریح و rbac را معمولی اضافه کردیم و هر دو زیر v1 و v2 سرو می‌شوند.
    (rbac_router, None),
    (chat_router, ["chat"]),
    # فاز ۶۱: فرم‌ساز و نظرسنجی + تماس تلفنی مدیریت‌شده
    (forms_router, None),
    (calls_router, None),
]

for _router, _tags in _ROUTERS:
    if _tags:
        app.include_router(_router, prefix=settings.api_prefix, tags=_tags)  # type: ignore[arg-type]
    else:
        app.include_router(_router, prefix=settings.api_prefix)

for _router, _ in _ROUTERS:
    app.include_router(_router, prefix=API_V2_PREFIX, include_in_schema=False)  # type: ignore[arg-type]

# فاز ۳۹: محافظ NUL داخلی‌تر از پاکت است تا رد 422 آن هم روی v2 پاکت‌بندی شود
app.add_middleware(NullByteGuardMiddleware)
# فاز ۴۲ - ADR-05 گام ۳: Idempotency-Key واقعی عملیات مالی — داخل‌تر از پاکت
# تا پاسخ بازپخش‌شده روی v2 هم عیناً پاکت‌بندی شود؛ بیرونی‌تر از محافظ NUL
# تا رد 422 آن هم رزرو کلید را آزاد کند
app.add_middleware(FinancialIdempotencyMiddleware)
# فاز ۴۳ - ADR-05 گام‌های ۱–۲: سقف نرخ سراسری Redis — بین پاکت و idempotency؛
# ۴۲۹ روی v2 پاکت‌بندی می‌شود و روی v1 هدرهای انقضا می‌گیرد؛ درخواستِ رد‌شده
# هرگز رزرو کلید idempotency نمی‌کند (بیرونی‌تر از میان‌افزار مالی)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(EnvelopeMiddleware)
# فاز ۴۱ - ADR-03 گام ۴: انقضای اعلام‌شده v1 (هدرهای Deprecation/Sunset/Warning
# فقط روی /api/v1؛ readonly = کلید اضطراری چرخه حذف) — بیرونی‌ترین لایه
app.add_middleware(V1DeprecationMiddleware)


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {"name": settings.app_name, "version": settings.app_version, "status": "ok"}
