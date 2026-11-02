import time
from datetime import datetime, timedelta, timezone
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_current_user_optional
from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    generate_activation_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    is_https_request,
    verify_password,
)
from app.db.session import get_db
from app.models.user import ActivationToken, AuthSession, User, UserStatus
from app.schemas.auth import (
    ActivateRequest,
    ChangePasswordRequest,
    LoginRequest,
    TokenResponse,
)
from app.services.audit import record_audit

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

REFRESH_COOKIE = "rosepsy_refresh"

# کنترل تلاش‌های ورود - بند ۴.۲ سند (کنترل در حافظه برای نسخه اول)
_failed_attempts: dict[str, list[float]] = {}
_attempts_lock = Lock()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _register_failed_attempt(key: str) -> None:
    now = time.monotonic()
    window = settings.login_attempt_window_minutes * 60
    with _attempts_lock:
        attempts = [t for t in _failed_attempts.get(key, []) if now - t < window]
        attempts.append(now)
        _failed_attempts[key] = attempts


def _is_blocked(key: str) -> bool:
    now = time.monotonic()
    window = settings.login_attempt_window_minutes * 60
    with _attempts_lock:
        attempts = [t for t in _failed_attempts.get(key, []) if now - t < window]
        return len(attempts) >= settings.login_max_attempts


def _clear_attempts(key: str) -> None:
    with _attempts_lock:
        _failed_attempts.pop(key, None)


def _set_refresh_cookie(response: Response, token: str, request: Request | None = None) -> None:
    # فیکس ورود روی HTTP ساده: کوکی Secure فقط وقتی واقعاً روی HTTPS هستیم.
    # روی http://130.185.73.157 مرورگر کوکیِ Secure را دور می‌ریخت و کاربر
    # پس از ورود در همان صفحهٔ لاگین می‌ماند (همان باگ رز هاب).
    secure = is_https_request(request) if request is not None else settings.cookie_secure
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        max_age=settings.refresh_token_expire_days * 24 * 3600,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/api",  # فاز ۳۹: هر دو نسخه v1/v2 — کوکی refresh نسخه‌agnostic است
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=REFRESH_COOKIE, path="/api")


def _revoke_all_sessions(db: Session, user_id) -> None:
    now = datetime.now(timezone.utc)
    sessions = db.scalars(
        select(AuthSession).where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
    ).all()
    for s in sessions:
        s.revoked_at = now


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)
) -> TokenResponse:
    username = payload.username.strip().lower()
    ip = _client_ip(request)
    key = f"{username}|{ip}"

    if _is_blocked(key):
        raise HTTPException(status_code=429, detail="تلاش‌های ناموفق زیاد است؛ کمی بعد دوباره تلاش کنید")

    user = db.scalar(select(User).where(User.username == username))
    invalid = HTTPException(status_code=401, detail="نام کاربری یا رمز عبور نادرست است")

    if user is None or not verify_password(user.password_hash, payload.password):
        _register_failed_attempt(key)
        record_audit(db, action="auth.login_failed", detail={"username": username, "ip": ip})
        raise invalid

    if user.status == UserStatus.DISABLED:
        record_audit(db, action="auth.login_failed", actor_user_id=user.id, detail={"reason": "disabled", "ip": ip})
        raise invalid

    if user.status == UserStatus.PENDING:
        raise HTTPException(status_code=403, detail="حساب در انتظار فعال‌سازی است")

    _clear_attempts(key)
    token, token_hash = generate_refresh_token()
    session = AuthSession(
        user_id=user.id,
        refresh_token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
        ip=ip,
        user_agent=(request.headers.get("user-agent") or "")[:400],
    )
    db.add(session)
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    record_audit(db, action="auth.login", actor_user_id=user.id, detail={"ip": ip})
    _set_refresh_cookie(response, token, request)
    return TokenResponse(
        access_token=create_access_token(user_id=str(user.id), auth_version=user.auth_version),
        must_change_password=user.must_change_password,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)) -> TokenResponse:
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise HTTPException(status_code=401, detail="نشستی یافت نشد؛ وارد شوید")

    session = db.scalar(select(AuthSession).where(AuthSession.refresh_token_hash == hash_token(raw)))
    now = datetime.now(timezone.utc)
    if session is None or session.revoked_at is not None or session.expires_at < now:
        raise HTTPException(status_code=401, detail="نشست منقضی شده است؛ وارد شوید")

    user = db.get(User, session.user_id)
    if user is None or user.status != UserStatus.ACTIVE:
        session.revoked_at = now
        db.commit()
        raise HTTPException(status_code=401, detail="حساب فعال نیست")

    # چرخش Refresh Token - بند ۴.۲ سند
    session.revoked_at = now
    new_token, new_hash = generate_refresh_token()
    new_session = AuthSession(
        user_id=user.id,
        refresh_token_hash=new_hash,
        expires_at=now + timedelta(days=settings.refresh_token_expire_days),
        ip=_client_ip(request),
        user_agent=(request.headers.get("user-agent") or "")[:400],
    )
    db.add(new_session)
    db.commit()

    _set_refresh_cookie(response, new_token, request)
    return TokenResponse(
        access_token=create_access_token(user_id=str(user.id), auth_version=user.auth_version),
        must_change_password=user.must_change_password,
    )


@router.get("/session-probe")
def session_probe(request: Request, db: Session = Depends(get_db)) -> dict:
    """فاز ۷۲ — پراپ بی‌صدای نشست برای بازیابی ورودِ یکپارچه (SSO) رز هاب.

    چرا این endpoint؟ اسپای پنل پس از فاز ۷۱ (حذف خطای 401 بی‌مصرف کنسول)
    وقتی توکن دسترسی (حافظه) و پرچم نشست (localStorage) ندارد، دیگر
    ``/auth/me`` را صدا نمی‌زند. ولی کاربرِ برگشته از رز هاب فقط کوکی
    refresh (HttpOnly) دارد و هیچ نشانه‌ای سمت کلاینت — بدون این پراپ نشستِ
    او هرگز بازیابی نمی‌شد و با وجود کوکی معتبر، در صفحهٔ ورود گیر می‌کرد
    (عارضهٔ میدانی: «از طریق SSO وارد صفحه می‌شود و وارد برنامه نمی‌شود»).

    قرارداد: همیشه 200 — حتی بدون کوکی. کلید «authenticated» تنها حقیقتِ
    نشست را می‌گوید تا کنسول مرورگر برای بازدیدکنندهٔ ناشناس هم بی‌خطا بماند
    (پراپ = یک درخواست 200 ارزان، نه یک 401 پرسر و صدا). اعتبارسنجی دقیقاً
    همان قواعد /auth/refresh است: کوکی موجود، نشست زنده (بدون ابطال/انقضا)
    و حساب ACTIVE. این endpoint توکن نمی‌چرخاند و اثر جانبی ندارد.
    """
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw:
        session = db.scalar(
            select(AuthSession).where(AuthSession.refresh_token_hash == hash_token(raw))
        )
        now = datetime.now(timezone.utc)
        if (
            session is not None
            and session.revoked_at is None
            and session.expires_at >= now
        ):
            user = db.get(User, session.user_id)
            if user is not None and user.status == UserStatus.ACTIVE:
                return {
                    "authenticated": True,
                    "must_change_password": user.must_change_password,
                }
    return {"authenticated": False}


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
) -> dict:
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw:
        session = db.scalar(select(AuthSession).where(AuthSession.refresh_token_hash == hash_token(raw)))
        if session and session.revoked_at is None:
            session.revoked_at = datetime.now(timezone.utc)
            db.commit()
            if user is not None:
                record_audit(db, action="auth.logout", actor_user_id=user.id)
    _clear_refresh_cookie(response)
    return {"status": "ok"}


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    # فاز ۵۲: دسترسی‌های مؤثر برای گیت‌کردن منو/صفحه‌های پنل (SYSTEM_ADMIN → *)
    from app.api.deps import user_permissions
    # فاز ۷۱: ماتریس منوها — {menu_key: level} برای فیلتر منوی پنل + دکمه‌ها
    from app.models.rbac import user_menu_levels
    # فاز ۷۴: سازمان کاربر برای ایزولاسیون دادهٔ سازمانی
    from app.models.org_contract import Organization

    org = db.get(Organization, user.organization_id) if user.organization_id else None
    return {
        "id": str(user.id),
        "username": user.username,
        "display_name": user.display_name,
        "email": user.email,
        "mobile": user.mobile,
        "status": user.status,
        "must_change_password": user.must_change_password,
        "roles": sorted(r.code for r in user.roles),
        "permissions": sorted(user_permissions(db, user)),
        "menu_permissions": user_menu_levels(db, user),
        "organization_id": str(user.organization_id) if user.organization_id else None,
        "organization_name": org.name if org else None,
    }


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    if not verify_password(user.password_hash, payload.current_password):
        raise HTTPException(status_code=400, detail="رمز عبور فعلی نادرست است")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="رمز جدید باید با رمز فعلی متفاوت باشد")

    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    user.auth_version += 1
    _revoke_all_sessions(db, user.id)
    db.commit()
    record_audit(db, action="auth.password_changed", actor_user_id=user.id)
    _clear_refresh_cookie(response)
    return {"status": "ok"}


@router.post("/activate")
def activate(payload: ActivateRequest, db: Session = Depends(get_db)) -> dict:
    token_hash = hash_token(payload.token.strip())
    activation = db.scalar(
        select(ActivationToken).where(
            ActivationToken.token_hash == token_hash,
            ActivationToken.used_at.is_(None),
            ActivationToken.expires_at > datetime.now(timezone.utc),
        )
    )
    if activation is None:
        raise HTTPException(status_code=400, detail="توکن فعال‌سازی نامعتبر یا منقضی است")

    user = db.get(User, activation.user_id)
    if user is None:
        raise HTTPException(status_code=400, detail="توکن فعال‌سازی نامعتبر است")

    user.password_hash = hash_password(payload.new_password)
    user.status = UserStatus.ACTIVE
    user.must_change_password = False
    user.auth_version += 1
    activation.used_at = datetime.now(timezone.utc)
    db.commit()
    record_audit(db, action="auth.activated", actor_user_id=user.id)
    return {"status": "ok"}


# ---------------- فاز ۲۶ - B02-lite: کد یک‌بارمصرف (OTP) ----------------

class OtpRequestPayload(BaseModel):
    mobile: str = Field(min_length=10, max_length=20)
    purpose: str = Field(default="booking", pattern=r"^(booking|login)$")


class OtpVerifyPayload(BaseModel):
    mobile: str = Field(min_length=10, max_length=20)
    code: str = Field(min_length=4, max_length=8)
    purpose: str = Field(default="booking", pattern=r"^(booking|login)$")


@router.post("/otp/request")
def otp_request(payload: OtpRequestPayload, request: Request, db: Session = Depends(get_db)) -> dict:
    """صدور کد یک‌بارمصرف - در حالت توسعه کد در پاسخ برمی‌گردد (آماده‌سازی D04)."""
    from app.services.otp import is_valid_mobile, normalize_mobile, request_otp

    mobile = normalize_mobile(payload.mobile)
    if not is_valid_mobile(mobile):
        raise HTTPException(status_code=422, detail="شماره موبایل معتبر نیست (نمونه: 09121234567)")
    res = request_otp(db, mobile, payload.purpose, ip=_client_ip(request))
    if res["rate_limited"]:
        raise HTTPException(status_code=429, detail="تعداد درخواست کد زیاد است؛ کمی بعد دوباره تلاش کنید")
    out: dict = {
        "status": "sent",
        "expires_in": settings.otp_code_ttl_seconds,
    }
    if res["dev_code"] is not None:
        out["dev_code"] = res["dev_code"]
        out["dev_notice"] = "حالت توسعه: کد به‌جای پیامک در پاسخ نمایش داده می‌شود"
    return out


@router.post("/otp/verify")
def otp_verify(
    payload: OtpVerifyPayload,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    """بررسی کد؛ در موفقیت توکن اثبات تأیید موبایل (یک‌بارمصرف) برمی‌گردد.

    فاز ۶۴: برای purpose=login نشست کامل صادر می‌شود (ورود دو عاملی پیامکی) —
    کد تأیید شد → کاربرِ دارای این موبایل پیدا و نشست (access + refresh cookie)
    باز می‌شود؛ همان مسیر امن login.
    """
    from app.services.otp import is_valid_mobile, normalize_mobile, verify_otp

    mobile = normalize_mobile(payload.mobile)
    if not is_valid_mobile(mobile):
        raise HTTPException(status_code=422, detail="شماره موبایل معتبر نیست")
    res = verify_otp(db, mobile, payload.purpose, payload.code)
    if res.get("reason") == "locked":
        raise HTTPException(status_code=429, detail="تلاش‌های ناموفق زیاد است؛ کد جدید درخواست کنید")
    if not res["ok"]:
        raise HTTPException(status_code=400, detail="کد وارد شده نادرست یا منقضی است")

    if payload.purpose == "login":
        user = db.scalar(
            select(User).where(User.mobile == mobile).order_by(User.created_at)
        )
        if user is None:
            record_audit(db, action="auth.otp_login_failed", detail={"reason": "no_user", "ip": _client_ip(request)})
            raise HTTPException(status_code=404, detail="حسابی با این شماره موبایل یافت نشد")
        if user.status == UserStatus.DISABLED:
            record_audit(db, action="auth.otp_login_failed", actor_user_id=user.id,
                         detail={"reason": "disabled", "ip": _client_ip(request)})
            raise HTTPException(status_code=403, detail="حساب غیرفعال است")
        if user.status == UserStatus.PENDING:
            raise HTTPException(status_code=403, detail="حساب در انتظار فعال‌سازی است")

        ip = _client_ip(request)
        token, token_hash = generate_refresh_token()
        session = AuthSession(
            user_id=user.id,
            refresh_token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
            ip=ip,
            user_agent=(request.headers.get("user-agent") or "")[:400],
        )
        db.add(session)
        user.last_login_at = datetime.now(timezone.utc)
        db.commit()
        record_audit(db, action="auth.login_otp", actor_user_id=user.id, detail={"ip": ip})
        _set_refresh_cookie(response, token, request)
        return TokenResponse(
            access_token=create_access_token(user_id=str(user.id), auth_version=user.auth_version),
            must_change_password=user.must_change_password,
        ).model_dump()

    return {
        "status": "verified",
        "verify_token": res["verify_token"],
        "expires_in": settings.otp_verify_token_seconds,
    }
