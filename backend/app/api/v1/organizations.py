"""فاز ۳۳/۳۴ - B21 + B21-plus سند جامع: سازمان‌ها، قراردادها، سهم پرداخت
و صورتحساب دوره‌ای سازمان.

قواعد پذیرش:
- slug سازمان یکتا (۴۰۹)؛ شناسه ملی سازمان در صورت ورود یکتا؛
- قرارداد: ۰ < درصد سهم ≤ ۱۰۰؛ بازه اعتبار معتبر (valid_to ≥ valid_from)؛
  وضعیت draft/active/terminated؛ «قرارداد منقضی یا پیش‌نویس در تقسیم سهم
  اعمال نمی‌شود»؛
- دامنه خدمت قرارداد: بدون ردیف = همه خدمات؛ با ردیف = فقط همان خدمات؛
- تقسیم سهم در ساخت سفارش (payments.create_order) snapshot می‌شود؛
- B21-plus (فاز ۳۴): صورتحساب دوره‌ای از سفارش‌های پرداخت‌شده دارای سهم
  در بازه snapshot می‌شود؛ هر سفارش حداکثر یک‌بار (uq)؛ صدور سند جدید
  نمی‌زند؛ تسویه سند می‌زند: Dr 1101 بانک | Cr 1104 دریافتنی سازمان؛
  تسویه فقط برای issued؛ تکرار ۴۰۹.
"""
import re
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.catalog import Service
from app.models.org_contract import Contract, ContractService, ContractTest, Organization
from app.models.org_statement import OrgStatement, OrgStatementItem, OrgStatementStatus
from app.models.payment import Order, OrderStatus
from app.models.psych_test import PsychTest
from app.models.user import User
from app.services.accounting import entry_for_org_statement

router = APIRouter(tags=["organizations"])

MANAGE_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER")
VIEW_ROLES = (*MANAGE_ROLES, "TECHNICAL_SUPERVISOR", "RECEPTION")


def _roles(actor) -> set[str]:
    return {r.code for r in actor.roles}


def _ensure_org_scope(actor, org_id) -> None:
    """فاز ۷۴ — ایزولاسیون سازمانی: کاربر منتسب‌شده به یک سازمان فقط به
    همان سازمان دسترسی دارد (SYSTEM_ADMIN همیشه بدون محدودیت)."""
    if "SYSTEM_ADMIN" in _roles(actor):
        return
    scope = actor.organization_id
    if scope is None:
        return
    try:
        target = uuid.UUID(str(org_id))
    except (TypeError, ValueError):
        return
    if target != scope:
        raise HTTPException(status_code=403, detail="دسترسی به این سازمان مجاز نیست")

_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,118}[a-z0-9])?$")


# ---------------------------------------------------------------- schemas
class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(min_length=2, max_length=120)
    national_id: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=200)
    address: str | None = Field(default=None, max_length=500)
    note: str | None = Field(default=None, max_length=500)
    is_active: bool = True


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    national_id: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=200)
    address: str | None = Field(default=None, max_length=500)
    note: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


class ContractCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    coverage_percent: float = Field(gt=0, le=100)
    coverage_cap_amount: int | None = Field(default=None, ge=0)
    valid_from: date
    valid_to: date | None = None
    notes: str | None = Field(default=None, max_length=1000)
    service_ids: list[uuid.UUID] = Field(default_factory=list)
    # فاز ۶۲: کدام آزمون‌ها برای سازمان باز باشد؛ خالی = همه آزمون‌ها
    test_ids: list[uuid.UUID] = Field(default_factory=list)


class ContractUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    coverage_percent: float | None = Field(default=None, gt=0, le=100)
    coverage_cap_amount: int | None = Field(default=None, ge=0)
    valid_from: date | None = None
    valid_to: date | None = None
    notes: str | None = Field(default=None, max_length=1000)
    status: str | None = None
    service_ids: list[uuid.UUID] | None = None
    test_ids: list[uuid.UUID] | None = None


# ---------------------------------------------------------------- helpers
def _validate_slug(slug: str) -> str:
    s = slug.strip().lower()
    if not _SLUG_RE.match(s):
        raise HTTPException(
            status_code=422, detail="slug فقط حروف کوچک لاتین، عدد و خط تیره است"
        )
    return s


def _contract_out(db: Session, c: Contract) -> dict:
    svc_rows = db.execute(
        select(ContractService, Service)
        .join(Service, Service.id == ContractService.service_id)
        .where(ContractService.contract_id == c.id)
        .order_by(Service.title)
    ).all()
    test_rows = db.execute(
        select(PsychTest)
        .join(ContractTest, ContractTest.test_id == PsychTest.id)
        .where(ContractTest.contract_id == c.id)
        .order_by(PsychTest.title)
    ).scalars().all()
    return {
        "id": str(c.id),
        "organization_id": str(c.organization_id),
        "organization_name": c.organization.name if c.organization else None,
        "title": c.title,
        "coverage_percent": float(c.coverage_percent),
        "coverage_cap_amount": float(c.coverage_cap_amount) if c.coverage_cap_amount else None,
        "valid_from": str(c.valid_from),
        "valid_to": str(c.valid_to) if c.valid_to else None,
        "status": c.status,
        "notes": c.notes,
        "services": [
            {"id": str(svc.id), "title": svc.title} for _cs, svc in svc_rows
        ],
        # فاز ۶۲: فهرست آزمون‌های باز این قرارداد؛ خالی = همه آزمون‌ها
        "tests": [{"id": str(t.id), "title": t.title} for t in test_rows],
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _org_out(db: Session, o: Organization) -> dict:
    contracts = db.scalars(
        select(Contract).where(Contract.organization_id == o.id).order_by(Contract.created_at)
    ).all()
    today = date.today()
    active_contract = next(
        (
            c
            for c in contracts
            if c.status == "active" and c.valid_from <= today and (c.valid_to is None or c.valid_to >= today)
        ),
        None,
    )
    # فاز ۶۲: آزمون‌های باز سازمان از قرارداد فعال مشتق می‌شود؛
    # None = قرارداد فعال ندارد؛ [] = همه آزمون‌ها باز؛ elif لیست = فقط همان‌ها.
    open_tests: list[dict] | None = None
    if active_contract is not None:
        rows = db.execute(
            select(PsychTest)
            .join(ContractTest, ContractTest.test_id == PsychTest.id)
            .where(ContractTest.contract_id == active_contract.id)
            .order_by(PsychTest.title)
        ).scalars().all()
        open_tests = [{"id": str(t.id), "title": t.title} for t in rows]
    return {
        "id": str(o.id),
        "name": o.name,
        "slug": o.slug,
        "national_id": o.national_id,
        "phone": o.phone,
        "email": o.email,
        "address": o.address,
        "note": o.note,
        "is_active": o.is_active,
        "contract_count": len(contracts),
        "active_contract": (
            {
                "id": str(active_contract.id),
                "title": active_contract.title,
                "coverage_percent": float(active_contract.coverage_percent),
                "valid_from": str(active_contract.valid_from),
                "valid_to": str(active_contract.valid_to) if active_contract.valid_to else None,
            }
            if active_contract
            else None
        ),
        "open_tests": open_tests,
        "created_at": o.created_at.isoformat() if o.created_at else None,
    }


def _validate_contract_dates(valid_from: date, valid_to: date | None) -> None:
    if valid_to is not None and valid_to < valid_from:
        raise HTTPException(
            status_code=422, detail="تاریخ پایان اعتبار نمی‌تواند پیش از تاریخ شروع باشد"
        )


def _set_contract_services(db: Session, contract: Contract, service_ids: list[uuid.UUID]) -> None:
    seen: set[uuid.UUID] = set()
    for sid in service_ids:
        if sid in seen:
            continue
        seen.add(sid)
        if db.get(Service, sid) is None:
            raise HTTPException(status_code=404, detail=f"خدمت یافت نشد: {sid}")
        exists = db.scalars(
            select(ContractService).where(
                ContractService.contract_id == contract.id, ContractService.service_id == sid
            )
        ).first()
        if exists is None:
            db.add(ContractService(contract_id=contract.id, service_id=sid))


def _set_contract_tests(db: Session, contract: Contract, test_ids: list[uuid.UUID]) -> None:
    """فاز ۶۲: ثبت آزمون‌های باز قرارداد؛ idempotent و بدون ردیف تکراری."""
    seen: set[uuid.UUID] = set()
    for tid in test_ids:
        if tid in seen:
            continue
        seen.add(tid)
        if db.get(PsychTest, tid) is None:
            raise HTTPException(status_code=404, detail=f"آزمون یافت نشد: {tid}")
        exists = db.scalars(
            select(ContractTest).where(
                ContractTest.contract_id == contract.id, ContractTest.test_id == tid
            )
        ).first()
        if exists is None:
            db.add(ContractTest(contract_id=contract.id, test_id=tid))


# ---------------------------------------------------------------- organizations
@router.get("/organizations")
def list_organizations(
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*VIEW_ROLES)),
) -> dict:
    orgs = db.scalars(select(Organization).order_by(Organization.name)).all()
    # فاز ۷۴ — ایزولاسیون: کاربر منتسب‌شده فقط سازمان خودش را می‌بیند
    if "SYSTEM_ADMIN" not in _roles(actor) and actor.organization_id is not None:
        orgs = [o for o in orgs if o.id == actor.organization_id]
    return {"items": [_org_out(db, o) for o in orgs]}


@router.post("/organizations", status_code=201)
def create_organization(
    payload: OrganizationCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    slug = _validate_slug(payload.slug)
    dup = db.scalars(select(Organization.id).where(Organization.slug == slug)).first()
    if dup is not None:
        raise HTTPException(status_code=409, detail="این slug قبلاً استفاده شده است")
    if payload.national_id:
        dup_nid = db.scalars(
            select(Organization.id).where(Organization.national_id == payload.national_id.strip())
        ).first()
        if dup_nid is not None:
            raise HTTPException(status_code=409, detail="این شناسه ملی قبلاً ثبت شده است")
    org = Organization(
        name=payload.name.strip(),
        slug=slug,
        national_id=payload.national_id.strip() if payload.national_id else None,
        phone=payload.phone,
        email=payload.email,
        address=payload.address,
        note=payload.note,
        is_active=payload.is_active,
        created_by=actor.id,
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return _org_out(db, org)


@router.patch("/organizations/{org_id}")
def update_organization(
    org_id: uuid.UUID,
    payload: OrganizationUpdate,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="سازمان یافت نشد")
    for field in ("name", "phone", "email", "address", "note"):
        value = getattr(payload, field)
        if value is not None:
            setattr(org, field, value.strip() if isinstance(value, str) else value)
    if payload.national_id is not None:
        nid = payload.national_id.strip()
        if nid:
            dup_nid = db.scalars(
                select(Organization.id).where(
                    Organization.national_id == nid, Organization.id != org.id
                )
            ).first()
            if dup_nid is not None:
                raise HTTPException(status_code=409, detail="این شناسه ملی قبلاً ثبت شده است")
            org.national_id = nid
    if payload.is_active is not None:
        org.is_active = payload.is_active
    db.commit()
    db.refresh(org)
    return _org_out(db, org)


# ---------------------------------------------------------------- contracts
@router.get("/organizations/{org_id}/contracts")
def list_contracts(
    org_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*VIEW_ROLES)),
) -> dict:
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="سازمان یافت نشد")
    _ensure_org_scope(actor, org_id)
    contracts = db.scalars(
        select(Contract).where(Contract.organization_id == org_id).order_by(Contract.created_at.desc())
    ).all()
    return {"items": [_contract_out(db, c) for c in contracts]}


@router.post("/organizations/{org_id}/contracts", status_code=201)
def create_contract(
    org_id: uuid.UUID,
    payload: ContractCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="سازمان یافت نشد")
    _validate_contract_dates(payload.valid_from, payload.valid_to)
    contract = Contract(
        organization_id=org_id,
        title=payload.title.strip(),
        coverage_percent=payload.coverage_percent,
        coverage_cap_amount=payload.coverage_cap_amount,
        valid_from=payload.valid_from,
        valid_to=payload.valid_to,
        status="draft",
        notes=payload.notes,
        created_by=actor.id,
    )
    db.add(contract)
    db.flush()
    _set_contract_services(db, contract, payload.service_ids)
    _set_contract_tests(db, contract, payload.test_ids)
    db.commit()
    db.refresh(contract)
    return _contract_out(db, contract)


@router.patch("/contracts/{contract_id}")
def update_contract(
    contract_id: uuid.UUID,
    payload: ContractUpdate,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    contract = db.get(Contract, contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail="قرارداد یافت نشد")
    if payload.status is not None and payload.status not in ("draft", "active", "terminated"):
        raise HTTPException(status_code=422, detail="وضعیت باید draft، active یا terminated باشد")
    for field in ("title", "notes"):
        value = getattr(payload, field)
        if value is not None:
            setattr(contract, field, value)
    if payload.coverage_percent is not None:
        contract.coverage_percent = payload.coverage_percent
    if payload.coverage_cap_amount is not None:
        contract.coverage_cap_amount = payload.coverage_cap_amount
    if payload.valid_from is not None:
        contract.valid_from = payload.valid_from
    if payload.valid_to is not None:
        contract.valid_to = payload.valid_to
    _validate_contract_dates(contract.valid_from, contract.valid_to)
    if payload.status is not None:
        # قرارداد منقضی/ملغی فعال نمی‌شود؛ فعال‌سازی فقط از پیش‌نویس
        if payload.status == "active" and contract.status == "terminated":
            raise HTTPException(status_code=422, detail="قرارداد ملغی قابل فعال‌سازی مجدد نیست")
        contract.status = payload.status
    if payload.service_ids is not None:
        _set_contract_services(db, contract, payload.service_ids)
        keep = set(payload.service_ids)
        for row in db.scalars(
            select(ContractService).where(ContractService.contract_id == contract.id)
        ).all():
            if row.service_id not in keep:
                db.delete(row)
    if payload.test_ids is not None:
        _set_contract_tests(db, contract, payload.test_ids)
        keep_tests = set(payload.test_ids)
        for row in db.scalars(
            select(ContractTest).where(ContractTest.contract_id == contract.id)
        ).all():
            if row.test_id not in keep_tests:
                db.delete(row)
    db.commit()
    db.refresh(contract)
    return _contract_out(db, contract)


# ---------------------------------------------------------------- statements (B21-plus، فاز ۳۴)
class StatementCreate(BaseModel):
    period_from: date
    period_to: date
    note: str | None = Field(default=None, max_length=500)


def _next_statement_number(db: Session) -> str:
    """شماره یکتای صورتحساب: ORG-<سال شمسی>-<ترتیب ۶ رقمی>."""
    from app.core.dates import gregorian_to_jalali
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    jy, _, _ = gregorian_to_jalali(now.year, now.month, now.day)
    for _ in range(30):
        rows = db.execute(
            text("SELECT COUNT(*) FROM org_statements WHERE statement_no LIKE :pfx"),
            {"pfx": f"ORG-{jy:04d}-%"},
        ).scalar() or 0
        candidate = f"ORG-{jy:04d}-{rows + 1:06d}"
        if db.scalars(select(OrgStatement.id).where(OrgStatement.statement_no == candidate)).first() is None:
            return candidate
    raise HTTPException(status_code=500, detail="تولید شماره صورتحساب ناموفق بود")


def _statement_out(st: OrgStatement) -> dict:
    return {
        "id": str(st.id),
        "statement_no": st.statement_no,
        "organization_id": str(st.organization_id),
        "period_from": str(st.period_from),
        "period_to": str(st.period_to),
        "status": st.status,
        "orders_count": int(st.orders_count or 0),
        "total_amount": int(st.total_amount or 0),
        "org_share_total": int(st.org_share_total or 0),
        "applicant_share_total": int(st.applicant_share_total or 0),
        "currency": st.currency,
        "journal_entry_id": str(st.journal_entry_id) if st.journal_entry_id else None,
        "note": st.note,
        "settled_at": st.settled_at.isoformat() if st.settled_at else None,
        "created_at": st.created_at.isoformat() if st.created_at else None,
        "items": [
            {
                "order_id": str(it.order_id),
                "order_number": it.order_number,
                "amount": int(it.amount or 0),
                "org_share_amount": int(it.org_share_amount or 0),
                "applicant_share_amount": int(it.applicant_share_amount or 0),
                "coverage_percent": float(it.coverage_percent) if it.coverage_percent is not None else None,
            }
            for it in st.items
        ],
    }


@router.post("/organizations/{org_id}/statements", status_code=201)
def create_statement(
    org_id: uuid.UUID,
    payload: StatementCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    """صورتحساب دوره‌ای سازمان — snapshot سفارش‌های پرداخت‌شده دارای سهم
    سازمان در بازه؛ هر سفارش حداکثر یک‌بار در کل صورتحساب‌ها (uq)."""
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="سازمان یافت نشد")
    if payload.period_to < payload.period_from:
        raise HTTPException(status_code=422, detail="تاریخ پایان بازه نمی‌تواند پیش از شروع باشد")
    start_dt = datetime.combine(payload.period_from, datetime.min.time())
    end_dt = datetime.combine(payload.period_to + timedelta(days=1), datetime.min.time())
    rows = db.execute(
        select(Order)
        .outerjoin(OrgStatementItem, OrgStatementItem.order_id == Order.id)
        .where(
            Order.organization_id == org_id,
            Order.status == OrderStatus.PAID,
            Order.org_share_amount.isnot(None),
            Order.org_share_amount > 0,
            Order.created_at >= start_dt,
            Order.created_at < end_dt,
            OrgStatementItem.id.is_(None),
        )
        .order_by(Order.created_at)
    ).scalars().all()
    if not rows:
        raise HTTPException(
            status_code=422,
            detail="سفارش قابل صورتحساب (پرداخت‌شده با سهم سازمان، بدون صورتحساب قبلی) در این بازه یافت نشد",
        )
    st = OrgStatement(
        statement_no=_next_statement_number(db),
        organization_id=org_id,
        period_from=payload.period_from,
        period_to=payload.period_to,
        status=OrgStatementStatus.ISSUED,
        orders_count=len(rows),
        total_amount=sum(int(o.amount or 0) for o in rows),
        org_share_total=sum(int(o.org_share_amount or 0) for o in rows),
        applicant_share_total=sum(int(o.applicant_share_amount or 0) for o in rows),
        note=payload.note,
        issued_by=actor.id,
    )
    db.add(st)
    db.flush()
    for o in rows:
        db.add(
            OrgStatementItem(
                statement_id=st.id,
                order_id=o.id,
                order_number=o.order_number,
                amount=int(o.amount or 0),
                org_share_amount=int(o.org_share_amount or 0),
                applicant_share_amount=int(o.applicant_share_amount or 0),
                coverage_percent=float(o.coverage_percent) if o.coverage_percent is not None else None,
            )
        )
    db.commit()
    db.refresh(st)
    return _statement_out(st)


@router.get("/organizations/{org_id}/statements")
def list_statements(
    org_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*VIEW_ROLES)),
) -> dict:
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="سازمان یافت نشد")
    _ensure_org_scope(actor, org_id)
    rows = db.scalars(
        select(OrgStatement)
        .where(OrgStatement.organization_id == org_id)
        .order_by(OrgStatement.created_at.desc())
    ).all()
    return {"items": [_statement_out(st) for st in rows]}


@router.get("/organizations/{org_id}/statements/{statement_id}")
def get_statement(
    org_id: uuid.UUID,
    statement_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*VIEW_ROLES)),
) -> dict:
    _ensure_org_scope(actor, org_id)
    st = db.get(OrgStatement, statement_id)
    if st is None or st.organization_id != org_id:
        raise HTTPException(status_code=404, detail="صورتحساب یافت نشد")
    return _statement_out(st)


@router.post("/statements/{statement_id}/settle")
def settle_statement(
    statement_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    """تسویه مطالبات با سند ۱۱۰۴ — Dr 1101 بانک | Cr 1104 دریافتنی سازمان؛
    idempotent با (source_type, source_id)؛ تسویه مجدد ۴۰۹."""
    st = db.get(OrgStatement, statement_id)
    if st is None:
        raise HTTPException(status_code=404, detail="صورتحساب یافت نشد")
    if st.status == OrgStatementStatus.SETTLED:
        raise HTTPException(status_code=409, detail="این صورتحساب قبلاً تسویه شده است")
    try:
        entry = entry_for_org_statement(db, st, commit=False)
    except Exception as exc:  # AccountingError و...
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if entry is None:
        db.rollback()
        raise HTTPException(status_code=422, detail="مبلغ صورتحساب برای تسویه صفر است")
    st.status = OrgStatementStatus.SETTLED
    st.journal_entry_id = entry.id
    st.settled_by = actor.id
    st.settled_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(st)
    out = _statement_out(st)
    out["journal_entry"] = {
        "id": str(entry.id),
        "entry_no": entry.entry_no,
        "kind": entry.kind,
        "source_type": entry.source_type,
    }
    return out


# ---------------------------------------------------------------- receivables
@router.get("/organizations/{org_id}/receivables")
def organization_receivables(
    org_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*MANAGE_ROLES, "TECHNICAL_SUPERVISOR")),
) -> dict:
    """مطالبه از سازمان: جمع سهم سازمان سفارش‌های پرداخت‌شده (بستانکاری سازمان)."""
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="سازمان یافت نشد")
    _ensure_org_scope(actor, org_id)
    rows = db.scalars(
        select(Order)
        .where(
            Order.organization_id == org_id,
            Order.status == OrderStatus.PAID,
            Order.org_share_amount.isnot(None),
        )
        .order_by(Order.created_at.desc())
        .limit(200)
    ).all()
    total_org = sum(int(o.org_share_amount or 0) for o in rows)
    total_amount = sum(int(o.amount) for o in rows)
    # فاز ۳۴ - B21-plus: تسویه‌شده از طریق صورتحساب‌های سازمان (سند ۱۱۰۴) کسر می‌شود
    settled_total = int(
        db.scalar(
            select(func.coalesce(func.sum(OrgStatement.org_share_total), 0)).where(
                OrgStatement.organization_id == org_id,
                OrgStatement.status == OrgStatementStatus.SETTLED,
            )
        )
        or 0
    )
    issued_total = int(
        db.scalar(
            select(func.coalesce(func.sum(OrgStatement.org_share_total), 0)).where(
                OrgStatement.organization_id == org_id,
                OrgStatement.status == OrgStatementStatus.ISSUED,
            )
        )
        or 0
    )
    statements = db.scalars(
        select(OrgStatement)
        .where(OrgStatement.organization_id == org_id)
        .order_by(OrgStatement.created_at.desc())
        .limit(50)
    ).all()
    return {
        "organization_id": str(org_id),
        "organization_name": org.name,
        "paid_orders_with_share": len(rows),
        "total_amount": total_amount,
        "org_share_total": total_org,
        "applicant_share_total": total_amount - total_org,
        "settled_total": settled_total,
        "issued_unsettled_total": issued_total,
        "outstanding_total": max(0, total_org - settled_total),
        "statements": [
            {
                "id": str(st.id),
                "statement_no": st.statement_no,
                "period_from": str(st.period_from),
                "period_to": str(st.period_to),
                "status": st.status,
                "orders_count": int(st.orders_count or 0),
                "org_share_total": int(st.org_share_total or 0),
                "created_at": st.created_at.isoformat() if st.created_at else None,
            }
            for st in statements
        ],
        "items": [
            {
                "order_id": str(o.id),
                "order_number": o.order_number,
                "title": o.title,
                "amount": int(o.amount),
                "coverage_percent": float(o.coverage_percent) if o.coverage_percent else None,
                "org_share_amount": int(o.org_share_amount or 0),
                "applicant_share_amount": int(o.applicant_share_amount or 0),
                "status": o.status,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in rows
        ],
    }
