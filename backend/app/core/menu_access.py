"""فاز ۷۱ — دروازهٔ ماتریس منوها (Menu Access Gate) به‌صورت میان‌افزار ASGI.

چرا میان‌افزار و نه دیپندنسی روی همهٔ روترها؟
- فقط مسیرهایی که واقعاً به یک منوی ماتریس تعلق دارند پردازش می‌شوند؛ بقیهٔ
  درخواست‌ها (سایت عمومی، auth، سلام سرویس، …) بدون هیچ هزینه‌ای رد می‌شوند؛
- کنترل «دیدن / خواندن / ویرایش» به‌صورت مرکزی و یکدست روی v1 و v2 اعمال
  می‌شود بدون آنکه تک‌تک endpointها دست‌کاری شوند.

قرارداد سطح‌ها (از app.core.menu_registry):
- POST/PUT/PATCH/DELETE → «ویرایش»
- GET/HEAD با آیدی UUID در مسیر (جزئیات رکورد) → «خواندن»
- بقیهٔ GET/HEAD (فهرست/آمار) → «دیدن»

قواعد امنیتی:
- درخواست بدون احراز هویت از گیت رد نمی‌شود — endpointهای محافظت‌شده خودشان
  401 می‌دهند و endpointهای عمومی باید برای مهمان‌ها کار کنند؛
- SYSTEM_ADMIN همیشه رد می‌شود (bypass) تا مدیر خودش را قفل نکند؛
- مسیرهای عمومیِ معرفی‌شده در ``public_prefixes`` هر رجیستری، همیشه بازند.
"""
from __future__ import annotations

import uuid

from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.menu_registry import LEVEL_RANK, resolve_menu


def _db_session():
    from app.db.session import SessionLocal

    return SessionLocal()


def _strip_api_prefix(path: str) -> str:
    from app.core.config import get_settings
    from app.core.envelope import API_V2_PREFIX

    settings = get_settings()
    for prefix in (settings.api_prefix, API_V2_PREFIX):
        if path == prefix:
            return "/"
        if path.startswith(prefix + "/"):
            return path[len(prefix):]
    return path


class MenuAccessMiddleware:
    """میان‌افزار ASGI خالص — بدون سربار BaseHTTPMiddleware."""

    def __init__(self, app):  # type: ignore[no-untyped-def]
        self.app = app

    async def __call__(self, scope, receive, send):  # type: ignore[no-untyped-def]
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = (scope.get("method") or "GET").upper()
        if method == "OPTIONS":
            await self.app(scope, receive, send)
            return

        path = _strip_api_prefix(scope.get("path") or "")
        resolved = resolve_menu(method, path)
        if resolved is None:
            await self.app(scope, receive, send)
            return

        menu_key, needed = resolved
        auth = ""
        for name, value in scope.get("headers") or []:
            if name == b"authorization":
                auth = value.decode("latin-1", "ignore")
                break
        if not auth.startswith("Bearer "):
            # مهمان — endpoint مقصد خودش 401/پاسخ عمومی می‌دهد
            await self.app(scope, receive, send)
            return

        denial = await self._check(menu_key, needed, auth[7:])
        if denial is not None:
            status, payload = denial
            response = JSONResponse(payload, status_code=status)
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)

    async def _check(self, menu_key: str, needed: str, token: str):  # type: ignore[no-untyped-def]
        """None = مجاز؛ در غیر این صورت (status, payload) رد."""
        from app.core.menu_registry import menu_title
        from app.core.security import decode_access_token
        from app.models.rbac import user_menu_levels
        from app.models.user import User, UserStatus

        try:
            payload = decode_access_token(token)
            user_id = uuid.UUID(str(payload["sub"]))
        except Exception:  # noqa: BLE001 — توکن خراب را endpoint مقصد جواب می‌دهد
            return None

        db = _db_session()
        try:
            user = db.get(User, user_id)
            if user is None or user.status != UserStatus.ACTIVE:
                return None
            levels = user_menu_levels(db, user)
            have = levels.get(menu_key)
            if have is not None and LEVEL_RANK.get(have, 0) >= LEVEL_RANK.get(needed, 1):
                return None
            title = menu_title(menu_key)
            detail = (
                f"سطح دسترسی شما به بخش «{title}» برای این عملیات کافی نیست "
                f"(لازم: {needed}). با مدیر سامانه تماس بگیرید."
            )
            return 403, {"detail": detail}
        except Exception:  # noqa: BLE001 — خطای فنی گیت هرگز سامانه را نمی‌بندد
            return None
        finally:
            db.close()
