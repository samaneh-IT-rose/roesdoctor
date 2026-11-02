"""فاز ۵۸ - پنل آزمون‌های سازمانی: برنامهٔ ارزیابی سازمان (کارتابل).

قواعد پذیرش:
- برنامهٔ آزمون متعلق به یک سازمان است؛ عنوان برای سازمان یکتا نیست اما
  حداقل یک آزمون الزام ندارد (می‌توان بعداً افزود)؛
- آزمون‌های برنامه فقط از ابزارهای «منتشرشده» مرکز آزمون انتخاب می‌شوند؛
- عضو می‌تواند بدون حساب کاربری باشد؛ در صورت پیوند به حساب، پیشرفت او
  (تکمیل آزمون‌های برنامه) از PsychAttempt محاسبه می‌شود؛
- مشاوران پروژه باید حساب فعال داشته باشند (برای گفتگوی آنلاین)؛
- سوالات پرتکرار (FAQ) با PUT جایگزین کامل می‌شود؛
- کارتابل (GET detail) همهٔ اجزا + پیشرفت اعضا را یک‌جا برمی‌گرداند.
"""
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.org_contract import Organization
from app.models.org_program import (
    OrgProgram,
    OrgProgramCounselor,
    OrgProgramFaq,
    OrgProgramMember,
    OrgProgramStatus,
    OrgProgramTest,
)
from app.models.psych_test import PsychAttempt, PsychStatus, PsychTest
from app.models.user import User, UserStatus

router = APIRouter(tags=["org-programs"])

MANAGE_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER")
VIEW_ROLES = (*MANAGE_ROLES, "TECHNICAL_SUPERVISOR", "RECEPTION", "COUNSELOR")
# فاز ۷۴: همهٔ نقش‌های ستادی — مبنای تفکیک «ستاد» از «عضو عادی برنامه»
STAFF_ROLES = (*VIEW_ROLES, "SYSTEM_ADMIN")


def _roles(actor) -> set[str]:
    return {r.code for r in actor.roles}


def _is_staff(actor) -> bool:
    return bool(_roles(actor) & set(STAFF_ROLES))


def _actor_org_scope(actor) -> uuid.UUID | None:
    """فاز ۷۴ — اسکوپ سازمانی کاربر؛ SYSTEM_ADMIN همیشه بدون محدودیت."""
    if "SYSTEM_ADMIN" in _roles(actor):
        return None
    return actor.organization_id


def _member_programs_stmt(actor):
    """برنامه‌هایی که کاربر عضو آن‌هاست (برای اعضای عادی مثل متقاضی)."""
    return select(OrgProgramMember.program_id).where(OrgProgramMember.user_id == actor.id)


# ---------------------------------------------------------------- schemas
class ProgramCreate(BaseModel):
    organization_id: str
    title: str = Field(min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=3000)
    guide_text: str | None = None
    due_date: date | None = None
    status: str = OrgProgramStatus.ACTIVE
    test_ids: list[str] = Field(default_factory=list)


class ProgramUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=3000)
    guide_text: str | None = None
    due_date: date | None = None
    status: str | None = None


class TestsSet(BaseModel):
    test_ids: list[str] = Field(default_factory=list)


class MemberCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    employee_code: str | None = Field(default=None, max_length=60)
    mobile: str | None = Field(default=None, max_length=30)
    unit: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=500)
    user_id: str | None = None


class CounselorCreate(BaseModel):
    user_id: str
    role_in_project: str = Field(default="مشاور", max_length=80)


class FaqSet(BaseModel):
    items: list[dict] = Field(default_factory=list)  # [{question, answer}]


# ---------------------------------------------------------------- helpers
def _parse_uuid(value: str, what: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"{what} نامعتبر است") from exc


def _get_program(db: Session, program_id: uuid.UUID) -> OrgProgram:
    p = db.get(OrgProgram, program_id)
    if p is None:
        raise HTTPException(status_code=404, detail="برنامهٔ آزمون یافت نشد")
    return p


def _member_progress(db: Session, program_id: uuid.UUID, user_id) -> tuple[int, int]:
    """پیشرفت عضو: تعداد آزمون‌های تکمیل‌شده از آزمون‌های برنامه."""
    if user_id is None:
        return (0, 0)
    total = int(
        db.scalar(
            select(func.count()).select_from(OrgProgramTest).where(OrgProgramTest.program_id == program_id)
        )
        or 0
    )
    if total == 0:
        return (0, 0)
    test_ids = select(OrgProgramTest.test_id).where(OrgProgramTest.program_id == program_id)
    done = int(
        db.scalar(
            select(func.count(func.distinct(PsychAttempt.test_id))).where(
                PsychAttempt.user_id == user_id,
                PsychAttempt.test_id.in_(test_ids),
            )
        )
        or 0
    )
    return (done, total)


def _program_summary(db: Session, p: OrgProgram) -> dict:
    org = db.get(Organization, p.organization_id)
    tests_count = int(
        db.scalar(select(func.count()).select_from(OrgProgramTest).where(OrgProgramTest.program_id == p.id)) or 0
    )
    members_count = int(
        db.scalar(select(func.count()).select_from(OrgProgramMember).where(OrgProgramMember.program_id == p.id)) or 0
    )
    counselors_count = int(
        db.scalar(
            select(func.count()).select_from(OrgProgramCounselor).where(OrgProgramCounselor.program_id == p.id)
        )
        or 0
    )
    faq_count = int(
        db.scalar(select(func.count()).select_from(OrgProgramFaq).where(OrgProgramFaq.program_id == p.id)) or 0
    )
    # میانگین پیشرفت اعضای دارای حساب
    members = db.scalars(
        select(OrgProgramMember).where(
            OrgProgramMember.program_id == p.id, OrgProgramMember.user_id.isnot(None)
        )
    ).all()
    progress_pct = 0
    if members:
        ratios = []
        for m in members:
            done, total = _member_progress(db, p.id, m.user_id)
            if total > 0:
                ratios.append(done / total)
        progress_pct = round(100 * sum(ratios) / len(ratios)) if ratios else 0
    return {
        "id": str(p.id),
        "organization_id": str(p.organization_id),
        "organization_name": org.name if org else None,
        "organization_slug": org.slug if org else None,
        "title": p.title,
        "description": p.description,
        "status": p.status,
        "due_date": str(p.due_date) if p.due_date else None,
        "tests_count": tests_count,
        "members_count": members_count,
        "counselors_count": counselors_count,
        "faq_count": faq_count,
        "progress_percent": progress_pct,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def _set_program_tests(db: Session, program_id: uuid.UUID, test_ids: list[str]) -> None:
    """جایگزینی کامل فهرست آزمون‌های برنامه (ترتیب ورودی حفظ می‌شود)."""
    seen: list[uuid.UUID] = []
    for raw in test_ids:
        tid = _parse_uuid(raw, "شناسهٔ آزمون")
        t = db.get(PsychTest, tid)
        if t is None:
            raise HTTPException(status_code=404, detail=f"آزمون یافت نشد: {raw}")
        if t.status != PsychStatus.PUBLISHED:
            raise HTTPException(
                status_code=422,
                detail=f"آزمون «{t.title}» منتشرشده نیست و نمی‌تواند به برنامه اضافه شود",
            )
        if tid not in seen:
            seen.append(tid)
    keep = set(seen)
    existing = {
        r.test_id: r
        for r in db.scalars(select(OrgProgramTest).where(OrgProgramTest.program_id == program_id)).all()
    }
    # حذف حذف‌شده‌ها
    for tid, row in existing.items():
        if tid not in keep:
            db.delete(row)
    # درج/به‌روزرسانی ترتیب
    for idx, tid in enumerate(seen):
        row = existing.get(tid)
        if row is None:
            db.add(OrgProgramTest(program_id=program_id, test_id=tid, sort_order=idx))
        else:
            row.sort_order = idx


# ---------------------------------------------------------------- programs
@router.get("/org-programs")
def list_programs(
    organization_id: str = Query(default="", max_length=64),
    status: str = Query(default="", max_length=20),
    q: str = Query(default="", max_length=100),
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*VIEW_ROLES)),
) -> dict:
    stmt = select(OrgProgram).order_by(OrgProgram.created_at.desc())
    # فاز ۷۴ — ایزولاسیون سازمانی + دسترسی عضو:
    # ۱) کاربر منتسب‌شده به سازمان فقط برنامه‌های همان سازمان را می‌بیند؛
    # ۲) عضو عادی برنامه (مثلاً متقاضی) فقط برنامه‌های خودش را می‌بیند.
    org_scope = _actor_org_scope(actor)
    if org_scope is not None:
        stmt = stmt.where(OrgProgram.organization_id == org_scope)
    if not _is_staff(actor):
        stmt = stmt.where(OrgProgram.id.in_(_member_programs_stmt(actor)))
    if organization_id:
        stmt = stmt.where(OrgProgram.organization_id == _parse_uuid(organization_id, "شناسهٔ سازمان"))
    if status:
        if status not in OrgProgramStatus.ALL:
            raise HTTPException(status_code=422, detail="وضعیت نامعتبر است")
        stmt = stmt.where(OrgProgram.status == status)
    if q.strip():
        stmt = stmt.where(OrgProgram.title.ilike(f"%{q.strip()}%"))
    rows = db.scalars(stmt).all()
    return {"items": [_program_summary(db, p) for p in rows]}


@router.post("/org-programs", status_code=201)
def create_program(
    payload: ProgramCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    org_id = _parse_uuid(payload.organization_id, "شناسهٔ سازمان")
    if db.get(Organization, org_id) is None:
        raise HTTPException(status_code=404, detail="سازمان یافت نشد")
    # فاز ۷۴: مدیر سازمانی که به یک سازمان منتسب است فقط برای همان سازمان برنامه می‌سازد
    org_scope = _actor_org_scope(actor)
    if org_scope is not None and org_id != org_scope:
        raise HTTPException(status_code=403, detail="ثبت برنامه برای سازمان دیگر مجاز نیست")
    if payload.status not in OrgProgramStatus.ALL:
        raise HTTPException(status_code=422, detail="وضعیت نامعتبر است")
    p = OrgProgram(
        organization_id=org_id,
        title=payload.title.strip(),
        description=payload.description,
        guide_text=payload.guide_text,
        due_date=payload.due_date,
        status=payload.status,
        created_by=actor.id,
    )
    db.add(p)
    db.flush()
    if payload.test_ids:
        _set_program_tests(db, p.id, payload.test_ids)
    db.commit()
    db.refresh(p)
    return _program_summary(db, p)


@router.get("/org-programs/{program_id}")
def get_program_workdesk(
    program_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*VIEW_ROLES)),
) -> dict:
    """کارتابل برنامهٔ سازمانی: برنامه + آزمون‌ها + مشاوران + اعضا + پیشرفت + FAQ."""
    p = _get_program(db, program_id)
    # فاز ۷۴ — کنترل دسترسی داده:
    org_scope = _actor_org_scope(actor)
    if org_scope is not None and p.organization_id != org_scope:
        raise HTTPException(status_code=403, detail="دسترسی به برنامه‌های این سازمان مجاز نیست")
    if not _is_staff(actor):
        member = db.scalars(
            select(OrgProgramMember).where(
                OrgProgramMember.program_id == p.id, OrgProgramMember.user_id == actor.id
            )
        ).first()
        if member is None:
            raise HTTPException(status_code=403, detail="فقط اعضای برنامه به کارتابل آن دسترسی دارند")
    out = _program_summary(db, p)
    org = db.get(Organization, p.organization_id)
    out["guide_text"] = p.guide_text

    # --- آزمون‌های برنامه
    test_rows = db.execute(
        select(OrgProgramTest, PsychTest)
        .join(PsychTest, PsychTest.id == OrgProgramTest.test_id)
        .where(OrgProgramTest.program_id == p.id)
        .order_by(OrgProgramTest.sort_order)
    ).all()
    out["tests"] = [
        {
            "id": str(pt.id),
            "test_id": str(t.id),
            "slug": t.slug,
            "title": t.title,
            "code": t.code,
            "description": t.description,
            "topic_name": None,
            "accent_color": t.accent_color,
            "estimated_minutes": t.estimated_minutes,
            "is_required": pt.is_required,
            "sort_order": pt.sort_order,
        }
        for pt, t in test_rows
    ]

    # --- مشاوران پروژه
    c_rows = db.execute(
        select(OrgProgramCounselor, User)
        .join(User, User.id == OrgProgramCounselor.user_id)
        .where(OrgProgramCounselor.program_id == p.id)
        .order_by(OrgProgramCounselor.created_at)
    ).all()
    out["counselors"] = [
        {
            "id": str(pc.id),
            "user_id": str(u.id),
            "display_name": u.display_name or u.username,
            "username": u.username,
            "role_in_project": pc.role_in_project,
        }
        for pc, u in c_rows
    ]

    # --- اعضا + پیشرفت
    members = db.scalars(
        select(OrgProgramMember).where(OrgProgramMember.program_id == p.id).order_by(OrgProgramMember.created_at)
    ).all()
    linked_users = {}
    if members:
        uids = [m.user_id for m in members if m.user_id]
        if uids:
            for u in db.scalars(select(User).where(User.id.in_(uids))).all():
                linked_users[u.id] = u
    member_items = []
    for m in members:
        done, total = _member_progress(db, p.id, m.user_id)
        u = linked_users.get(m.user_id) if m.user_id else None
        member_items.append(
            {
                "id": str(m.id),
                "user_id": str(m.user_id) if m.user_id else None,
                "username": u.username if u else None,
                "full_name": m.full_name,
                "employee_code": m.employee_code,
                "mobile": m.mobile,
                "unit": m.unit,
                "note": m.note,
                "done_count": done,
                "total_tests": total,
                "progress_percent": round(100 * done / total) if total else 0,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
        )
    out["members"] = member_items

    # --- سوالات پرتکرار
    faqs = db.scalars(
        select(OrgProgramFaq).where(OrgProgramFaq.program_id == p.id).order_by(OrgProgramFaq.sort_order)
    ).all()
    out["faqs"] = [
        {"id": str(f.id), "question": f.question, "answer": f.answer, "sort_order": f.sort_order}
        for f in faqs
    ]
    return out


@router.patch("/org-programs/{program_id}")
def update_program(
    program_id: uuid.UUID,
    payload: ProgramUpdate,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    p = _get_program(db, program_id)
    if payload.title is not None:
        p.title = payload.title.strip()
    if payload.description is not None:
        p.description = payload.description
    if payload.guide_text is not None:
        p.guide_text = payload.guide_text
    if payload.due_date is not None:
        p.due_date = payload.due_date
    if payload.status is not None:
        if payload.status not in OrgProgramStatus.ALL:
            raise HTTPException(status_code=422, detail="وضعیت نامعتبر است")
        p.status = payload.status
    db.commit()
    db.refresh(p)
    return _program_summary(db, p)


@router.delete("/org-programs/{program_id}")
def delete_program(
    program_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    p = _get_program(db, program_id)
    db.delete(p)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- tests
@router.put("/org-programs/{program_id}/tests")
def set_program_tests(
    program_id: uuid.UUID,
    payload: TestsSet,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    p = _get_program(db, program_id)
    _set_program_tests(db, p.id, payload.test_ids)
    db.commit()
    return {"ok": True, "tests_count": len(payload.test_ids)}


# ---------------------------------------------------------------- members
@router.post("/org-programs/{program_id}/members", status_code=201)
def add_member(
    program_id: uuid.UUID,
    payload: MemberCreate,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    p = _get_program(db, program_id)
    user_id = None
    if payload.user_id:
        uid = _parse_uuid(payload.user_id, "شناسهٔ کاربر")
        u = db.get(User, uid)
        if u is None:
            raise HTTPException(status_code=404, detail="کاربر یافت نشد")
        dup = db.scalars(
            select(OrgProgramMember).where(
                OrgProgramMember.program_id == p.id, OrgProgramMember.user_id == uid
            )
        ).first()
        if dup is not None:
            raise HTTPException(status_code=409, detail="این کاربر قبلاً به برنامه اضافه شده است")
        user_id = uid
    m = OrgProgramMember(
        program_id=p.id,
        user_id=user_id,
        full_name=payload.full_name.strip(),
        employee_code=(payload.employee_code or "").strip() or None,
        mobile=(payload.mobile or "").strip() or None,
        unit=(payload.unit or "").strip() or None,
        note=payload.note,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return {
        "id": str(m.id),
        "full_name": m.full_name,
        "user_id": str(m.user_id) if m.user_id else None,
    }


@router.delete("/org-programs/{program_id}/members/{member_id}")
def remove_member(
    program_id: uuid.UUID,
    member_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    m = db.get(OrgProgramMember, member_id)
    if m is None or m.program_id != program_id:
        raise HTTPException(status_code=404, detail="عضو یافت نشد")
    db.delete(m)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- counselors
@router.post("/org-programs/{program_id}/counselors", status_code=201)
def add_counselor(
    program_id: uuid.UUID,
    payload: CounselorCreate,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    p = _get_program(db, program_id)
    uid = _parse_uuid(payload.user_id, "شناسهٔ کاربر")
    u = db.get(User, uid)
    if u is None or u.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد یا فعال نیست")
    dup = db.scalars(
        select(OrgProgramCounselor).where(
            OrgProgramCounselor.program_id == p.id, OrgProgramCounselor.user_id == uid
        )
    ).first()
    if dup is not None:
        raise HTTPException(status_code=409, detail="این مشاور قبلاً به پروژه اضافه شده است")
    pc = OrgProgramCounselor(program_id=p.id, user_id=uid, role_in_project=payload.role_in_project.strip() or "مشاور")
    db.add(pc)
    db.commit()
    db.refresh(pc)
    return {
        "id": str(pc.id),
        "user_id": str(uid),
        "display_name": u.display_name or u.username,
        "role_in_project": pc.role_in_project,
    }


@router.delete("/org-programs/{program_id}/counselors/{counselor_id}")
def remove_counselor(
    program_id: uuid.UUID,
    counselor_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    pc = db.get(OrgProgramCounselor, counselor_id)
    if pc is None or pc.program_id != program_id:
        raise HTTPException(status_code=404, detail="مشاور پروژه یافت نشد")
    db.delete(pc)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- FAQ
@router.put("/org-programs/{program_id}/faq")
def set_program_faq(
    program_id: uuid.UUID,
    payload: FaqSet,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    """جایگزینی کامل سوالات پرتکرار برنامه."""
    p = _get_program(db, program_id)
    items: list[tuple[str, str]] = []
    for i, raw in enumerate(payload.items):
        q = str(raw.get("question", "")).strip()
        a = str(raw.get("answer", "")).strip()
        if not q or not a:
            raise HTTPException(status_code=422, detail="سوال و پاسخ هر ردیف الزامی است")
        items.append((q[:500], a))
    for f in db.scalars(select(OrgProgramFaq).where(OrgProgramFaq.program_id == p.id)).all():
        db.delete(f)
    for idx, (q, a) in enumerate(items):
        db.add(OrgProgramFaq(program_id=p.id, question=q, answer=a, sort_order=idx))
    db.commit()
    return {"ok": True, "faq_count": len(items)}
