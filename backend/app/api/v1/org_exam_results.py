"""فاز ۷۴ - آزمون‌های برگزارشده سازمانی (منوی جداگانه برای مدیران سازمان).

هدف: مدیر هر سازمان بتواند فقط آزمون‌های سازمانی «خودش» را ببیند — فهرست
برنامه‌های برگزارشده + نتیجهٔ هر عضو در هر آزمون.

قواعد دسترسی:
- نقش‌های ستادی (SYSTEM_ADMIN/ORG_MANAGER/RECEPTION/TECHNICAL_SUPERVISOR/
  COUNSELOR) با ماتریس منوها گیت می‌شوند (دروازهٔ مرکزی + require_roles)؛
- ایزولاسیون داده: اگر ``users.organization_id`` کاربر ست شده باشد، فقط
  برنامه‌های همان سازمان برمی‌گردد (SYSTEM_ADMIN همیشه همه را می‌بیند)؛
- اعضای عادی برنامه (مثلاً متقاضی) فقط برنامه‌هایی را می‌بینند که عضو آن‌ها
  هستند و فقط ردیف خودشان در نتایج ظاهر می‌شود.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.org_contract import Organization
from app.models.org_program import (
    OrgProgram,
    OrgProgramMember,
    OrgProgramStatus,
    OrgProgramTest,
)
from app.models.psych_test import PsychAttempt, PsychTest
from app.models.user import User

router = APIRouter(tags=["org-exam-results"])

VIEW_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER", "TECHNICAL_SUPERVISOR", "RECEPTION", "COUNSELOR")

STAFF_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR")


def _roles(actor) -> set[str]:
    return {r.code for r in actor.roles}


def _actor_org_id(actor: User) -> uuid.UUID | None:
    """اسکوپ سازمانی کاربر — SYSTEM_ADMIN همیشه بدون محدودیت."""
    if "SYSTEM_ADMIN" in _roles(actor):
        return None
    return actor.organization_id


def _is_program_member(db: Session, program_id, user_id) -> bool:
    return (
        db.scalar(
            select(func.count())
            .select_from(OrgProgramMember)
            .where(OrgProgramMember.program_id == program_id, OrgProgramMember.user_id == user_id)
        )
        or 0
    ) > 0


def _member_done_tests(db: Session, program_id, user_id) -> tuple[int, int, dict]:
    """(تعداد تکمیل‌شده، کل آزمون‌ها، نقشهٔ test_id → آخرین تلاش)"""
    test_rows = db.execute(
        select(OrgProgramTest, PsychTest)
        .join(PsychTest, PsychTest.id == OrgProgramTest.test_id)
        .where(OrgProgramTest.program_id == program_id)
        .order_by(OrgProgramTest.sort_order)
    ).all()
    total = len(test_rows)
    attempts = {}
    if user_id is not None and total:
        test_ids = [t.id for _, t in test_rows]
        rows = db.scalars(
            select(PsychAttempt)
            .where(
                PsychAttempt.user_id == user_id,
                PsychAttempt.test_id.in_(test_ids),
            )
            .order_by(PsychAttempt.created_at.desc())
        ).all()
        for a in rows:  # اولین ردیف هر آزمون = آخرین تلاش
            if a.test_id not in attempts:
                attempts[a.test_id] = a
    done = sum(1 for _, t in test_rows if t.id in attempts)
    return done, total, {str(k): v for k, v in attempts.items()}


def _program_out(db: Session, p: OrgProgram) -> dict:
    org = db.get(Organization, p.organization_id)
    tests_count = int(
        db.scalar(select(func.count()).select_from(OrgProgramTest).where(OrgProgramTest.program_id == p.id)) or 0
    )
    members = db.scalars(
        select(OrgProgramMember).where(
            OrgProgramMember.program_id == p.id, OrgProgramMember.user_id.isnot(None)
        )
    ).all()
    done_members = 0
    ratios = []
    for m in members:
        done, total, _ = _member_done_tests(db, p.id, m.user_id)
        if total > 0:
            ratios.append(done / total)
            if done >= total:
                done_members += 1
    progress_pct = round(100 * sum(ratios) / len(ratios)) if ratios else 0
    return {
        "id": str(p.id),
        "organization_id": str(p.organization_id),
        "organization_name": org.name if org else None,
        "title": p.title,
        "description": p.description,
        "status": p.status,
        "due_date": str(p.due_date) if p.due_date else None,
        "tests_count": tests_count,
        "members_count": len(members),
        "completed_members": done_members,
        "progress_percent": progress_pct,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


@router.get("/org-exam-results")
def list_org_exam_results(
    status: str = Query(default="", max_length=20),
    q: str = Query(default="", max_length=100),
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*VIEW_ROLES)),
) -> dict:
    stmt = select(OrgProgram).order_by(OrgProgram.created_at.desc())
    org_id = _actor_org_id(actor)
    if org_id is not None:
        stmt = stmt.where(OrgProgram.organization_id == org_id)
    roles = _roles(actor)
    if not (roles & set(STAFF_ROLES)):
        # اعضای عادی (مثلاً متقاضی): فقط برنامه‌هایی که عضو آن‌ها هستند
        stmt = stmt.where(
            OrgProgram.id.in_(
                select(OrgProgramMember.program_id).where(OrgProgramMember.user_id == actor.id)
            )
        )
    if status:
        if status not in OrgProgramStatus.ALL:
            raise HTTPException(status_code=422, detail="وضعیت نامعتبر است")
        stmt = stmt.where(OrgProgram.status == status)
    if q.strip():
        stmt = stmt.where(OrgProgram.title.ilike(f"%{q.strip()}%"))
    rows = db.scalars(stmt).all()
    return {"items": [_program_out(db, p) for p in rows]}


@router.get("/org-exam-results/{program_id}")
def get_org_exam_result(
    program_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*VIEW_ROLES)),
) -> dict:
    p = db.get(OrgProgram, program_id)
    if p is None:
        raise HTTPException(status_code=404, detail="برنامهٔ آزمون یافت نشد")
    org_id = _actor_org_id(actor)
    if org_id is not None and p.organization_id != org_id:
        raise HTTPException(status_code=403, detail="دسترسی به آزمون‌های این سازمان مجاز نیست")
    roles = _roles(actor)
    is_member_only = not (roles & set(STAFF_ROLES))
    if is_member_only and not _is_program_member(db, p.id, actor.id):
        raise HTTPException(status_code=403, detail="دسترسی مجاز نیست")

    out = _program_out(db, p)

    # آزمون‌های برنامه
    test_rows = db.execute(
        select(OrgProgramTest, PsychTest)
        .join(PsychTest, PsychTest.id == OrgProgramTest.test_id)
        .where(OrgProgramTest.program_id == p.id)
        .order_by(OrgProgramTest.sort_order)
    ).all()
    out["tests"] = [
        {
            "test_id": str(t.id),
            "slug": t.slug,
            "title": t.title,
            "code": t.code,
        }
        for _, t in test_rows
    ]

    # اعضا + نتیجهٔ هر عضو در هر آزمون
    members = db.scalars(
        select(OrgProgramMember)
        .where(OrgProgramMember.program_id == p.id)
        .order_by(OrgProgramMember.created_at)
    ).all()
    linked_users = {}
    if members:
        uids = [m.user_id for m in members if m.user_id]
        if uids:
            for u in db.scalars(select(User).where(User.id.in_(uids))).all():
                linked_users[u.id] = u
    member_items = []
    for m in members:
        if is_member_only and m.user_id != actor.id:
            continue  # عضو عادی فقط ردیف خودش را می‌بیند
        done, total, attempts = _member_done_tests(db, p.id, m.user_id)
        u = linked_users.get(m.user_id) if m.user_id else None
        per_test = []
        for _, t in test_rows:
            a = attempts.get(str(t.id))
            per_test.append(
                {
                    "test_id": str(t.id),
                    "title": t.title,
                    "done": a is not None,
                    "score": float(a.score) if a is not None and a.score is not None else None,
                    "interpretation_label": a.interpretation_label if a is not None else None,
                    "completed_at": a.created_at.isoformat() if a is not None else None,
                }
            )
        member_items.append(
            {
                "id": str(m.id),
                "user_id": str(m.user_id) if m.user_id else None,
                "username": u.username if u else None,
                "full_name": m.full_name,
                "employee_code": m.employee_code,
                "unit": m.unit,
                "done_count": done,
                "total_tests": total,
                "progress_percent": round(100 * done / total) if total else 0,
                "tests": per_test,
            }
        )
    out["members"] = member_items
    return out
