"""ورود یکپارچه (SSO) با رز هاب — Rose Hub

پروتکل نسخه پایه (BASIC) طبق «docs/sso-integration-fa.md» در مخزن رز هاب:
رز هاب کاربرِ احرازهویت‌شده را با ``?sso_token=<JWT HS256>`` به این سامانه
برمی‌گرداند. توکن با clientSecret اختصاصی سامانه (rose-psy-5c3f9b) امضا شده،
اعتبار ۵ دقیقه دارد و فقط یک‌بار باید مصرف شود. پس از اعتبارسنجی، حساب کاربر
پیدا یا ساخته شده و نشست عادی سامانه (AuthSession + refresh cookie) برقرار
می‌شود — یعنی کاربر با همان هویت رز هاب، بدون رمز جداگانه وارد Rosepsy می‌شود.

نقش‌ها: بر اساس نقش کاربر در رز هاب، نقش محلی معادل به‌صورت جمع‌شونده
اختصاص داده می‌شود (SUPER_ADMIN→SYSTEM_ADMIN، UNIT_MANAGER→ORG_MANAGER،
سایر نقش‌ها→COUNSELOR). بدون این نگاشت، کاربر SSO نقش محلی ندارد و پنل
با «دسترسی مجاز نیست» بسته می‌شود.

فاز ۶۵ — انتقال مشخصات کامل: توکن رز هاب علاوه بر email/name/role/nationalId،
حالا ``mobile``، ``province``، ``provinceCode`` و ``clinic`` را هم حمل می‌کند.
در هر ورود SSO، حساب کاربر (display_name، mobile) و پروندهٔ مشاور متناظر
(Counselor) بر اساس کد ملی پیدا یا ساخته و بروزرسانی می‌شود — نام و نام
خانوادگی، موبایل، استان (کد رسمی از جدول provinces) و کلینک محل خدمت.
منبع حقیقت این فیلدها رز هاب است؛ خطای همگام‌سازی ورود را نمی‌شکند.

مسیرها:
- ``GET  /api/v1/auth/rose-sso?sso_token=...`` — جریان مرورگری؛ پس از ورود
  به ``/panel`` ریدایرکت می‌کند (پارامتر توکن از نشانی پاک می‌شود).
- ``POST /api/v1/auth/rose-sso`` با بدنه ``{"token": ...}`` — برای استفاده
  برنامه‌نویسی‌شده از سمت SPA.

فاز ۷۲ — رفع باگ «کاربر SSO وارد برنامه نمی‌شود»:
- مقصد دکمهٔ SSO (و ریدایرکت بدون‌توکنِ همین مسیر) دیگر launch مستقیم نیست؛
  صفحهٔ ورود خودِ درگاه رز هاب روی نشانی عمومی است با ``next=`` مسیر launch.
  launch مستقیم برای کاربرِ واردنشده در رز هاب ``307 → http://localhost:8082``
  می‌داد که در مرورگر کاربر باز نمی‌شود و جریان می‌شکست.
- بازیابی نشست در اسپای پنل: کاربرِ برگشته فقط کوکی refresh دارد (توکن دسترسی
  در حافظه است و پرچم نشست در localStorage ست نشده)؛ پس از فاز ۷۱ اسپای دیگر
  /auth/me را کورکورانه صدا نمی‌زد و نشست او گم می‌شد. ترمیم: پراپ بی‌صدای
  ``GET /auth/session-probe`` (همیشه 200 — بدون 401 کنسول) در بوت اسپای؛ اگر
  نشست زنده بود توکن با /auth/refresh بازیابی و ورود کامل می‌شود.
"""

import logging
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    is_https_request,
)
from app.db.session import get_db
from app.models.branch import Branch
from app.models.location import Province
from app.models.people import Counselor
from app.models.user import AuthSession, Role, User, UserStatus
from app.services.audit import record_audit
from app.services.counselor_import import (
    _norm_province_name,
    normalize_province_code,
)

router = APIRouter(prefix="/auth", tags=["rose-sso"])
settings = get_settings()

REFRESH_COOKIE = "rosepsy_refresh"  # همان کوکی مسیر /api در auth.py

# ---------------------------------------------------------------------------
# نگاشت نقش رز هاب → نقش‌های محلی رز سای (جمع‌شونده)
# - کاربرِ ساخته/پیدا‌شده از مسیر SSO اگر نقش محلی نداشته باشد، پنل با
#   «دسترسی مجاز نیست» بسته می‌شود؛ پس بر اساس نقش تأییدشده در توکن رز هاب،
#   نقش محلی معادل اختصاص می‌یابد.
# - نقش‌های دستیِ اضافه‌شده توسط مدیر رز سای حذف نمی‌شوند.
# - SYSTEM_ADMIN در effective_permissions همیشه دسترسی کامل دارد.
# ---------------------------------------------------------------------------
ROSE_HUB_ROLE_MAP = {
    "SUPER_ADMIN": ["SYSTEM_ADMIN"],
    "UNIT_MANAGER": ["ORG_MANAGER"],
    "THERAPIST": ["COUNSELOR"],
    "STAFF": ["COUNSELOR"],
    "TEACHER": ["COUNSELOR"],
    "EXTERNAL": ["COUNSELOR"],
}
DEFAULT_SSO_ROLES = ["COUNSELOR"]
SSO_ROLE_TITLES = {
    "SYSTEM_ADMIN": "مدیر سامانه",
    "ORG_MANAGER": "مدیر سازمان",
    "COUNSELOR": "مشاور",
}


def _ensure_sso_roles(db: Session, user: User, claims: dict) -> None:
    """اختصاص نقش محلی معادل نقش رز هاب (فقط نقش‌های جاافتاده اضافه می‌شوند)."""
    rh_role = (claims.get("role") or "").strip().upper()
    wanted = ROSE_HUB_ROLE_MAP.get(rh_role, DEFAULT_SSO_ROLES)
    have = {r.code for r in user.roles}
    missing = [code for code in wanted if code not in have]
    if not missing:
        return
    for code in missing:
        role = db.get(Role, code)
        if role is None:
            role = Role(code=code, title=SSO_ROLE_TITLES.get(code, code))
            db.add(role)
            db.flush()
        user.roles.append(role)
    db.commit()


class RoseSSORequest(BaseModel):
    token: str


def _decode_rose_hub_token(raw: str) -> dict:
    """اعتبارسنجی توکن رز هاب — امضا، مخاطب (aud)، صادرکننده (iss) و انقضا."""
    try:
        return jwt.decode(
            raw,
            settings.rose_hub_client_secret,
            algorithms=["HS256"],
            audience=settings.rose_hub_client_id,
            issuer="rose-hub",
            leeway=60,
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=401,
            detail="توکن ورود یکپارچه نامعتبر یا منقضی است؛ دوباره از رز هاب وارد شوید",
        )


def _find_or_create_user(db: Session, claims: dict) -> User:
    email = (claims.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=422, detail="توکن ورود یکپارچه فاقد ایمیل است")

    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        # ساخت خودکار حساب بر اساس هویت تأییدشده رز هاب؛ گذرواژه تصادفی
        # غیرقابل حدس (ورود فقط از مسیر SSO/بازیابی رمز ممکن است)
        base = email.split("@")[0][:80].replace(" ", "") or "rosehub"
        username = base
        i = 1
        while db.scalar(select(User).where(User.username == username)) is not None:
            i += 1
            username = f"{base}{i}"
        user = User(
            username=username,
            display_name=(claims.get("name") or email)[:200],
            email=email,
            password_hash=hash_password(os.urandom(24).hex()),
            status=UserStatus.ACTIVE,
            must_change_password=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    if user.status == UserStatus.DISABLED:
        raise HTTPException(status_code=403, detail="حساب کاربری شما غیرفعال است")
    return user


logger = logging.getLogger(__name__)


def _sync_profile_from_rose_hub(db: Session, user: User, claims: dict) -> None:
    """فاز ۶۵: همگام‌سازی مشخصات کامل کاربر از توکن رز هاب.

    - حساب کاربر: display_name (نام و نام خانوادگی) و mobile (موبایل)؛
    - پروندهٔ مشاور: بر اساس کد ملی (nationalId) پیدا یا ساخته می‌شود؛
      بعد از آن نام/نام خانوادگی، موبایل، استان (کد رسمی دو رقمی از جدول
      provinces — با کد یا نام) و کلینک محل خدمت بروزرسانی می‌شود و
      پرونده به حساب کاربر متصل می‌گردد؛ در صورت موجود بودن شعبهٔ کلینیک
      همان استان (فاز ۶۶) و خالی‌بودن branch_id، پرونده به آن شعبه هم
      متصل می‌شود.

    فیلد خالی در توکن یعنی «مقداری در رز هاب ثبت نشده» — مقدار محلی پاک
    نمی‌شود تا دادهٔ موجود با ورود بعدی از بین نرود. منبع حقیقت در تعارض،
    مقدار توکن است.
    """
    name = (claims.get("name") or "").strip()
    mobile = (claims.get("mobile") or "").strip()
    national_id = (claims.get("nationalId") or "").strip()
    province = (claims.get("province") or "").strip()
    province_code_raw = (claims.get("provinceCode") or "").strip()
    clinic = (claims.get("clinic") or "").strip()

    # ---------- حساب کاربر ----------
    if name and user.display_name != name[:200]:
        user.display_name = name[:200]
    if mobile and user.mobile != mobile[:20]:
        user.mobile = mobile[:20]

    # ---------- پروندهٔ مشاور: پیدا کردن ----------
    counselor: Counselor | None = None
    if national_id:
        counselor = db.scalar(select(Counselor).where(Counselor.national_id == national_id))
    if counselor is None:
        counselor = db.scalar(select(Counselor).where(Counselor.user_id == user.id))
    if counselor is None and national_id:
        # پروندهٔ بدون کد ملی که کد مشاورش از همین کد ملی ساخته شده
        counselor = db.scalar(
            select(Counselor).where(Counselor.counselor_code == f"C-{national_id}")
        )

    # ---------- پروندهٔ مشاور: ساختن ----------
    if counselor is None and national_id:
        parts = name.split()
        counselor = Counselor(
            counselor_code=f"C-{national_id}",
            first_name=(parts[0] if parts else "کاربر")[:100],
            last_name=(" ".join(parts[1:]) if len(parts) > 1 else (parts[0] if parts else "رز هاب"))[:100],
            national_id=national_id,
            status="active",
        )
        db.add(counselor)
        db.flush()

    # ---------- پروندهٔ مشاور: بروزرسانی ----------
    if counselor is not None:
        if name:
            parts = name.split()
            counselor.first_name = parts[0][:100]
            counselor.last_name = (" ".join(parts[1:]) if len(parts) > 1 else parts[0])[:100]
        if national_id and not counselor.national_id:
            counselor.national_id = national_id
        if mobile:
            counselor.work_mobile = mobile[:20]
        if not counselor.email and user.email:
            counselor.email = user.email
        if province or province_code_raw:
            resolved = normalize_province_code(province_code_raw or None)
            if resolved is None and province:
                code_by_name = {
                    _norm_province_name(p.name): p.code
                    for p in db.scalars(select(Province)).all()
                }
                resolved = code_by_name.get(_norm_province_name(province))
            if resolved:
                counselor.province_code = resolved
                # فاز ۶۶: اتصال به شعبهٔ کلینیک همان استان — فقط اگر پرونده هنوز
                # شعبه‌ای نداشته باشد؛ تخصیص دستی/سید مدیر رز سای بازنویسی نمی‌شود.
                if counselor.branch_id is None:
                    branch = db.scalar(
                        select(Branch).where(Branch.province_code == resolved).limit(1)
                    )
                    if branch is not None:
                        counselor.branch_id = branch.id
        if clinic:
            counselor.clinic = clinic[:200]
        if counselor.user_id is None:
            counselor.user_id = user.id

    db.commit()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _open_session(db: Session, user: User, request: Request) -> str:
    """ساخت AuthSession و بازگرداندن refresh token (همان الگوی login)."""
    token, token_hash = generate_refresh_token()
    session = AuthSession(
        user_id=user.id,
        refresh_token_hash=token_hash,
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.refresh_token_expire_days),
        ip=_client_ip(request),
        user_agent=(request.headers.get("user-agent") or "")[:400],
    )
    db.add(session)
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    return token


def _set_refresh_cookie(response: Response, token: str, request: Request) -> None:
    # فیکس ورود یکپارچه روی HTTP ساده: کوکی Secure فقط روی HTTPS واقعی —
    # روی http://130.185.73.157 مرورگر کوکیِ Secure را دور می‌ریخت و کاربر
    # پس از تأیید توکن باز هم به صفحهٔ ورود برمی‌گشت (همان باگ رز هاب).
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        max_age=settings.refresh_token_expire_days * 24 * 3600,
        httponly=True,
        secure=is_https_request(request),
        samesite="lax",
        path="/api",
    )


def _issue_login(db: Session, raw_token: str, request: Request, response: Response):
    payload = _decode_rose_hub_token(raw_token)
    user = _find_or_create_user(db, payload)
    _ensure_sso_roles(db, user, payload)
    try:
        _sync_profile_from_rose_hub(db, user, payload)
    except Exception:  # noqa: BLE001 — همگام‌سازی پروفایل هرگز ورود را نمی‌شکند
        db.rollback()
        logger.exception("rose-hub profile sync failed for user %s", user.id)
    refresh = _open_session(db, user, request)
    record_audit(
        db,
        action="auth.rose_sso",
        actor_user_id=user.id,
        detail={"ip": _client_ip(request), "via": "rose-hub", "jti": payload.get("jti")},
    )
    _set_refresh_cookie(response, refresh, request)
    return user


@router.get("/rose-sso")
def rose_sso_redirect(
    request: Request,
    sso_token: str = "",
    db: Session = Depends(get_db),
):
    """جریان مرورگری: اعتبارسنجی توکن، برقراری نشست و ریدایرکت به برنامه."""
    if not sso_token:
        # ورود مستقیم → هدایت به رز هاب برای احراز هویت (جریان SP-initiated)
        return RedirectResponse(settings.rose_hub_launch_url)
    # مقصد: پنل سامانه — پس از برقراری نشست، اسپای پنل با کوکی refresh
    # به‌طور خودکار وارد می‌شود؛ پارامتر sso_token هم از نشانی پاک می‌شود.
    response = RedirectResponse("/panel", status_code=303)
    _issue_login(db, sso_token, request, response)
    return response


@router.post("/rose-sso")
def rose_sso_api(
    payload: RoseSSORequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    user = _issue_login(db, payload.token, request, response)
    return {
        "access_token": create_access_token(
            user_id=str(user.id), auth_version=user.auth_version
        ),
        "token_type": "bearer",
        "must_change_password": user.must_change_password,
    }
