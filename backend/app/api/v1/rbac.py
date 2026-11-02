"""فاز ۵۲ - API مدیریت نقش‌ها و ماتریس دسترسی (پشتیبان رابط گرافیکی پنل).

- ``GET  /rbac/permissions``           کاتالوگ دسترسی‌ها گروه‌بندی‌شده بر بخش
- ``GET  /rbac/roles``                  فهرست نقش‌ها با ماتریس و data_scope
- ``POST /rbac/roles``                  ساخت نقش سفارشی
- ``PUT  /rbac/roles/{code}``           ویرایش عنوان/scope/ماتریس دسترسی
- ``DELETE /rbac/roles/{code}``         حذف نقش سفارشی (بدون کاربر متصل)

همهٔ روت‌ها با ``require_perm("roles.manage")`` (یا users.view برای خواندن)
محافظت می‌شوند؛ SYSTEM_ADMIN به‌صورت ذاتی دسترسی کامل دارد.
"""
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_perm, user_permissions
from app.core.menu_registry import (
    LEVEL_TITLES,
    LEVEL_RANK,
    MENU_GROUPS,
    MENU_LEVELS,
    is_menu_key,
    menu_title,
)
from app.db.session import get_db
from app.models.rbac import (
    DATA_SCOPES,
    DATA_SCOPE_TITLES,
    Permission,
    RoleMenuPermission,
    role_permissions_table,
)
from app.models.user import SYSTEM_ROLE_CODES, Role, User, user_roles_table
from app.services.audit import record_audit

router = APIRouter(prefix="/rbac", tags=["rbac"])

_ROLE_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,49}$")


class RoleUpsert(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    data_scope: str = "all"
    permissions: list[str] = []


class MenuMatrixUpsert(BaseModel):
    """فاز ۷۱ — ذخیرهٔ ماتریس منوهای یک نقش: {menu_key: level}."""

    menus: dict[str, str | None] = Field(default_factory=dict)


def _role_out(db: Session, role: Role, member_count: int | None = None) -> dict:
    perms = sorted(p.code for p in role.permissions)
    out: dict = {
        "code": role.code,
        "title": role.title,
        "data_scope": role.data_scope,
        "data_scope_title": DATA_SCOPE_TITLES.get(role.data_scope, role.data_scope),
        "permissions": perms,
        "is_system": role.code in SYSTEM_ROLE_CODES,
    }
    if member_count is not None:
        out["member_count"] = member_count
    return out


def _get_role_or_404(db: Session, code: str) -> Role:
    role = db.get(Role, code)
    if role is None:
        raise HTTPException(status_code=404, detail="نقش یافت نشد")
    return role


def _validate_scope(scope: str) -> None:
    if scope not in DATA_SCOPES:
        raise HTTPException(
            status_code=422,
            detail=f"سطح داده نامعتبر است؛ مقادیر مجاز: {', '.join(DATA_SCOPES)}",
        )


def _validate_perm_codes(db: Session, codes: list[str]) -> None:
    known = set(db.scalars(select(Permission.code)).all())
    unknown = [c for c in codes if c not in known]
    if unknown:
        raise HTTPException(status_code=422, detail=f"دسترسی نامعتبر: {', '.join(unknown)}")


@router.get("/permissions")
def list_permissions(
    db: Session = Depends(get_db),
    _actor: User = Depends(require_perm("roles.view", "users.view")),
) -> dict:
    """کاتالوگ دسترسی‌ها گروه‌بندی‌شده — ستون‌های ماتریس گرافیکی."""
    rows = db.scalars(select(Permission).order_by(Permission.section, Permission.sort, Permission.code)).all()
    sections: list[dict] = []
    order: list[str] = []
    by_section: dict[str, list[dict]] = {}
    for p in rows:
        if p.section not in by_section:
            by_section[p.section] = []
            order.append(p.section)
        by_section[p.section].append({"code": p.code, "title": p.title})
    for s in order:
        sections.append({"section": s, "permissions": by_section[s]})
    return {"sections": sections, "total": len(rows)}


@router.get("/roles")
def list_roles(
    db: Session = Depends(get_db),
    _actor: User = Depends(require_perm("roles.view", "users.view")),
) -> dict:
    roles = db.scalars(select(Role).order_by(Role.code)).all()
    counts = dict(
        db.execute(
            select(user_roles_table.c.role_code, func.count())
            .group_by(user_roles_table.c.role_code)
        ).all()
    )
    return {"items": [_role_out(db, r, counts.get(r.code, 0)) for r in roles]}


@router.get("/me/permissions")
def my_permissions(
    db: Session = Depends(get_db),
    actor: User = Depends(require_perm("*")),
) -> dict:
    """دسترسی‌های مؤثر کاربر جاری — برای گیت‌کردن منو و دکمه‌های پنل."""
    return {"permissions": sorted(user_permissions(db, actor))}


@router.put("/roles/{code}")
def update_role(
    code: str,
    payload: RoleUpsert,
    db: Session = Depends(get_db),
    actor: User = Depends(require_perm("roles.manage")),
) -> dict:
    role = _get_role_or_404(db, code)
    _validate_scope(payload.data_scope)
    _validate_perm_codes(db, payload.permissions)

    role.title = payload.title.strip()
    role.data_scope = payload.data_scope
    rows = db.scalars(select(Permission).where(Permission.code.in_(payload.permissions))).all()
    role.permissions = list(rows)
    db.commit()
    record_audit(
        db, action="rbac.role_updated", actor_user_id=actor.id,
        entity_type="role", entity_id=code,
        detail={"permissions": sorted(p.code for p in rows), "data_scope": payload.data_scope},
    )
    return _role_out(db, role)


@router.post("/roles/{code}", status_code=201)
def create_role_with_code(
    code: str,
    payload: RoleUpsert,
    db: Session = Depends(get_db),
    actor: User = Depends(require_perm("roles.manage")),
) -> dict:
    code = code.strip().upper()
    if not _ROLE_CODE_RE.match(code):
        raise HTTPException(
            status_code=422,
            detail="کد نقش باید حروف لاتین بزرگ/زیرخط، بین ۳ تا ۵۰ نویسه باشد (مثال: HR_MANAGER)",
        )
    if db.get(Role, code) is not None:
        raise HTTPException(status_code=409, detail="این کد نقش قبلاً ثبت شده است")
    _validate_scope(payload.data_scope)
    _validate_perm_codes(db, payload.permissions)

    role = Role(code=code, title=payload.title.strip(), data_scope=payload.data_scope)
    rows = db.scalars(select(Permission).where(Permission.code.in_(payload.permissions))).all()
    role.permissions = list(rows)
    db.add(role)
    db.commit()
    record_audit(
        db, action="rbac.role_created", actor_user_id=actor.id,
        entity_type="role", entity_id=code,
        detail={"permissions": sorted(p.code for p in rows)},
    )
    return _role_out(db, role)


@router.delete("/roles/{code}")
def delete_role(
    code: str,
    db: Session = Depends(get_db),
    actor: User = Depends(require_perm("roles.manage")),
) -> dict:
    role = _get_role_or_404(db, code)
    if role.code in SYSTEM_ROLE_CODES:
        raise HTTPException(status_code=403, detail="نقش‌های سیستمی قابل حذف نیستند")
    members = db.scalar(
        select(func.count()).select_from(
            select(user_roles_table.c.user_id).where(user_roles_table.c.role_code == code).subquery()
        )
    ) or 0
    if members:
        raise HTTPException(
            status_code=409,
            detail=f"این نقش به {members} کاربر متصل است؛ ابتدا نقش کاربران را تغییر دهید",
        )
    db.delete(role)
    db.commit()
    record_audit(
        db, action="rbac.role_deleted", actor_user_id=actor.id,
        entity_type="role", entity_id=code,
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# فاز ۷۱ — ماتریس منوها و زیرمنوها (دیدن / خواندن / ویرایش) برای هر نقش
# ---------------------------------------------------------------------------
@router.get("/menu-catalog")
def menu_catalog(
    db: Session = Depends(get_db),
    _actor: User = Depends(require_perm("roles.view", "roles.manage", "users.view")),
) -> dict:
    """نقشهٔ کامل منوها و زیرمنوهای پنل — ردیف‌های ماتریس گرافیکی فاز ۷۱."""
    groups: list[dict] = []
    for group in MENU_GROUPS:
        groups.append({
            "key": group["key"],
            "title": group["title"],
            "items": [
                {
                    "key": item["key"],
                    "title": item["title"],
                    "path": item["path"],
                    "self_service": item.self_service,
                }
                for item in group["items"]
            ],
        })
    return {
        "groups": groups,
        "levels": [{"value": lv, "title": LEVEL_TITLES[lv]} for lv in MENU_LEVELS],
        "total": sum(len(g["items"]) for g in groups),
    }


def _role_menu_rows(db: Session, code: str) -> dict[str, str]:
    rows = db.scalars(
        select(RoleMenuPermission).where(RoleMenuPermission.role_code == code)
    ).all()
    return {r.menu_key: r.level for r in rows}


@router.get("/roles/{code}/menus")
def get_role_menus(
    code: str,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_perm("roles.view", "roles.manage", "users.view")),
) -> dict:
    """ماتریس منوهای یک نقش — {menu_key: level}؛ SYSTEM_ADMIN همیشه قفل/کامل."""
    role = _get_role_or_404(db, code)
    if role.code == "SYSTEM_ADMIN":
        return {
            "role_code": role.code,
            "menus": {k: "edit" for k in (i["key"] for g in MENU_GROUPS for i in g["items"])},
            "locked": True,
        }
    return {"role_code": role.code, "menus": _role_menu_rows(db, role.code), "locked": False}


@router.put("/roles/{code}/menus")
def put_role_menus(
    code: str,
    payload: MenuMatrixUpsert,
    db: Session = Depends(get_db),
    actor: User = Depends(require_perm("roles.manage")),
) -> dict:
    """ذخیرهٔ ماتریس منوهای نقش — مقدار null/حذف کلید یعنی «هیچ» (منو پنهان)."""
    role = _get_role_or_404(db, code)
    if role.code == "SYSTEM_ADMIN":
        raise HTTPException(
            status_code=422,
            detail="ماتریس نقش مدیر سامانه (SYSTEM_ADMIN) همیشه کامل است و قابل تغییر نیست",
        )
    unknown = sorted({k for k in payload.menus if not is_menu_key(k)})
    if unknown:
        raise HTTPException(status_code=422, detail=f"کلید منوی نامعتبر: {', '.join(unknown)}")
    bad_levels = sorted({lv for lv in payload.menus.values() if lv and lv not in MENU_LEVELS})
    if bad_levels:
        raise HTTPException(
            status_code=422,
            detail=f"سطح نامعتبر: {', '.join(bad_levels)}؛ مقادیر مجاز: {', '.join(MENU_LEVELS)}",
        )

    current = {r.menu_key: r for r in db.scalars(
        select(RoleMenuPermission).where(RoleMenuPermission.role_code == role.code)
    ).all()}
    changed: list[str] = []
    for menu_key, level in payload.menus.items():
        row = current.get(menu_key)
        if not level:  # None/""/"none" → حذف ردیف یعنی «هیچ»
            if row is not None:
                db.delete(row)
                changed.append(f"{menu_key}:none")
            continue
        if row is None:
            db.add(RoleMenuPermission(role_code=role.code, menu_key=menu_key, level=level))
            changed.append(f"{menu_key}:{level}")
        elif row.level != level:
            row.level = level
            changed.append(f"{menu_key}:{level}")
    db.commit()
    record_audit(
        db, action="rbac.role_menus_updated", actor_user_id=actor.id,
        entity_type="role", entity_id=role.code, detail={"menus": changed},
    )
    return {
        "role_code": role.code,
        "menus": _role_menu_rows(db, role.code),
        "locked": False,
        "changed": changed,
    }
