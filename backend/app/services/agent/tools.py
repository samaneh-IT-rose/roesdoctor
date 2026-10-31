"""فاز ۵۳ - رجیستری ابزارهای عامل (الگوی Tool Registry سند dsh).

هر ابزار:
- یک تابع پایتونی با امضای ``(db, actor, args) -> dict``؛
- شِمای پارامتر (JSON-Schema سبک) برای معرفی به مدل؛
- برچسب فارسی + سیاست دسترسی: ``staff=True`` یعنی فقط نقش‌های مجاز کارکنان؛
- «فقط‌خواندنی» — هیچ ابزاری داده می‌نویسد یا تغییر نمی‌دهد.

ابزارهای کاربر عادی فقط دادهٔ خودِ کاربر را برمی‌گردانند (data_scope=own
به‌صورت ساختاری تضمین شده چون کوئری‌ها با actor.id فیلتر می‌شوند).
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment, AppointmentStatus
from app.models.branch import Branch, BranchStatus
from app.models.catalog import Service, ServiceStatus
from app.models.case import Case, CaseStatus
from app.models.payment import Order
from app.models.topics import ServiceTopic
from app.models.user import User
from app.models.wallet import Wallet

STAFF_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION", "COUNSELOR", "TECHNICAL_SUPERVISOR")

STATUS_FA = {
    "pending": "در انتظار پرداخت",
    "paid": "پرداخت‌شده",
    "cancelled": "لغو‌شده",
    "failed": "ناموفق",
    "scheduled": "رزروشده",
    "done": "انجام‌شده",
    "no_show": "عدم حضور",
    "new": "جدید",
    "awaiting_assignment": "در انتظار ارجاع",
    "active": "فعال",
    "suspended": "معلق",
    "closed": "بسته",
    "archived": "بایگانی",
}


@dataclass
class Tool:
    """یک ابزار عامل — الگوی typed tool در dsh."""

    name: str
    title: str
    description: str
    parameters: dict[str, Any]
    func: Callable[..., dict]
    staff_only: bool = False
    staff_roles: tuple[str, ...] = STAFF_ROLES


def _fmt_money(v) -> str:
    try:
        return f"{int(v):,}"
    except (TypeError, ValueError):
        return str(v)


# ----------------------------------------------------------------- ابزارهای عمومی (کاربر)
def tool_search_services(db: Session, actor: User, args: dict) -> dict:
    """جست‌وجوی خدمات فعال سامانه با کلیدواژه."""
    q = (args.get("query") or "").strip()
    limit = min(int(args.get("limit") or 8), 15)
    stmt = select(Service).where(Service.status == ServiceStatus.ACTIVE)
    if q:
        stmt = stmt.where(Service.title.ilike(f"%{q}%"))
    rows = db.scalars(stmt.order_by(Service.title).limit(limit)).all()
    return {
        "count": len(rows),
        "services": [
            {
                "title": s.title,
                "code": s.code,
                "duration_minutes": s.duration_minutes,
                "session_type": {"in_person": "حضوری", "online": "آنلاین", "phone": "تلفنی"}.get(s.session_type, s.session_type),
            }
            for s in rows
        ],
    }


def tool_list_branches(db: Session, actor: User, args: dict) -> dict:
    """فهرست شعب منتشرشده (با فیلتر اختیاری شهر)."""
    city = (args.get("city") or "").strip()
    stmt = select(Branch).where(Branch.status == BranchStatus.PUBLISHED)
    if city:
        stmt = stmt.where(Branch.city.ilike(f"%{city}%"))
    rows = db.scalars(stmt.order_by(Branch.name).limit(15)).all()
    return {
        "count": len(rows),
        "branches": [
            {
                "name": b.name,
                "city": b.city,
                "address": b.address,
                "phone": b.phone,
            }
            for b in rows
        ],
    }


def tool_my_orders(db: Session, actor: User, args: dict) -> dict:
    """خلاصهٔ سفارش‌های خودِ کاربر (فقط دادهٔ خودش)."""
    limit = min(int(args.get("limit") or 10), 20)
    rows = db.scalars(
        select(Order)
        .where(Order.owner_user_id == actor.id)
        .order_by(Order.created_at.desc())
        .limit(limit)
    ).all()
    return {
        "count": len(rows),
        "orders": [
            {
                "order_number": o.order_number,
                "title": o.title,
                "status": STATUS_FA.get(o.status, o.status),
                "payable_amount": _fmt_money(o.payable_amount),
                "created_at": o.created_at.strftime("%Y-%m-%d") if o.created_at else None,
            }
            for o in rows
        ],
    }


def tool_my_appointments(db: Session, actor: User, args: dict) -> dict:
    """نوبت‌های آیندهٔ خودِ کاربر از طریق سفارش‌های متصل به نوبت."""
    now = datetime.now(timezone.utc)
    appt_ids = db.scalars(
        select(Order.appointment_id).where(
            Order.owner_user_id == actor.id, Order.appointment_id.isnot(None)
        )
    ).all()
    if not appt_ids:
        return {"count": 0, "appointments": [], "note": "نوبتی برای شما یافت نشد"}
    rows = db.scalars(
        select(Appointment).where(
            Appointment.id.in_(appt_ids),
            Appointment.scheduled_at >= now,
        ).order_by(Appointment.scheduled_at).limit(10)
    ).all()
    return {
        "count": len(rows),
        "appointments": [
            {
                "scheduled_at": a.scheduled_at.strftime("%Y-%m-%d %H:%M") if a.scheduled_at else None,
                "status": STATUS_FA.get(a.status, a.status),
            }
            for a in rows
        ],
    }


def tool_wallet_balance(db: Session, actor: User, args: dict) -> dict:
    """مانده کیف پول خودِ کاربر."""
    w = db.scalar(select(Wallet).where(Wallet.user_id == actor.id))
    if w is None:
        return {"balance": "0", "currency": "IRR", "note": "کیف پولی برای شما ساخته نشده است"}
    return {"balance": _fmt_money(w.balance), "currency": w.currency}


def tool_service_topics(db: Session, actor: User, args: dict) -> dict:
    """دسته‌بندی موضوعی خدمات (کاتالوگ عمومی)."""
    rows = db.execute(
        select(Service.title, ServiceTopic.topic_id)
        .join(ServiceTopic, ServiceTopic.service_id == Service.id)
        .where(Service.status == ServiceStatus.ACTIVE)
        .limit(60)
    ).all()
    topics: dict[str, list[str]] = {}
    for title, topic_id in rows:
        topics.setdefault(str(topic_id), []).append(title)
    return {"topics": [{"topic_id": k, "services": v[:6]} for k, v in list(topics.items())[:12]]}


# ----------------------------------------------------------------- ابزارهای کارکنان
def tool_cases_summary(db: Session, actor: User, args: dict) -> dict:
    """خلاصهٔ آماری پرونده‌ها بر اساس وضعیت (فقط کارکنان) — بدون محتوای بالینی."""
    rows = db.execute(
        select(Case.status, func.count()).group_by(Case.status)
    ).all()
    items = [{"status": STATUS_FA.get(s, s), "count": int(c)} for s, c in rows]
    return {"summary": items, "total": sum(i["count"] for i in items)}


def tool_no_show_risk(db: Session, actor: User, args: dict) -> dict:
    """ریسک عدم‌حضور نوبت‌های آینده (فقط کارکنان؛ همان منطق B27 قاعده‌محور)."""
    days = min(int(args.get("days_ahead") or 7), 30)
    now = datetime.now(timezone.utc)
    until = now + timedelta(days=days)
    upcoming = db.scalars(
        select(Appointment).where(
            Appointment.status == AppointmentStatus.SCHEDULED,
            Appointment.scheduled_at >= now,
            Appointment.scheduled_at <= until,
        ).order_by(Appointment.scheduled_at).limit(200)
    ).all()
    high = 0
    for a in upcoming:
        prev = db.scalar(
            select(func.count()).select_from(Appointment).where(
                Appointment.case_id == a.case_id,
                Appointment.status == AppointmentStatus.NO_SHOW,
            )
        ) or 0
        if 10 + 25 * int(prev) >= 60:
            high += 1
    return {
        "window_days": days,
        "upcoming_appointments": len(upcoming),
        "high_risk_count": high,
        "note": "امتیاز قاعده‌محور (۱۰ پایه + ۲۵ به‌ازای هر عدم‌حضور قبلی؛ سقف ۹۵)؛ بالای ۶۰ = ریسک بالا",
    }


def tool_upcoming_appointments_staff(db: Session, actor: User, args: dict) -> dict:
    """نوبت‌های آیندهٔ کل سامانه (فقط کارکنان؛ بدون دادهٔ بالینی)."""
    days = min(int(args.get("days_ahead") or 7), 30)
    now = datetime.now(timezone.utc)
    rows = db.scalars(
        select(Appointment).where(
            Appointment.status == AppointmentStatus.SCHEDULED,
            Appointment.scheduled_at >= now,
            Appointment.scheduled_at <= now + timedelta(days=days),
        ).order_by(Appointment.scheduled_at).limit(15)
    ).all()
    return {
        "count": len(rows),
        "appointments": [
            {
                "scheduled_at": a.scheduled_at.strftime("%Y-%m-%d %H:%M") if a.scheduled_at else None,
                "status": STATUS_FA.get(a.status, a.status),
            }
            for a in rows
        ],
    }


# ------------------------------------------------------- فاز ۷۰ - ابزارهای جدید
def tool_find_counselor(db: Session, actor: User, args: dict) -> dict:
    """مشاوران قابل رزرو با لینک صفحهٔ اختصاصی (برای هدایت به رزرو آنلاین)."""
    from app.core.config import get_settings
    from app.services.qualification import bookable_counselors

    limit = min(int(args.get("limit") or 5), 10)
    base = (get_settings().public_base_url or "").rstrip("/")
    counselors = bookable_counselors(db)[:limit]
    return {
        "count": len(counselors),
        "booking_url": f"{base}/booking" if base else "/booking",
        "counselors": [
            {
                "name": f"{c.first_name} {c.last_name}".strip(),
                "specialty": c.specialty or c.professional_title or "",
                "profile_url": (f"{base}/specialist/{c.id}" if base else f"/specialist/{c.id}"),
            }
            for c in counselors
        ],
    }


def tool_my_psych_results(db: Session, actor: User, args: dict) -> dict:
    """نتایج آزمون‌های خودِ کاربر (عنوان، نمره، تفسیر، زمان) — فقط دادهٔ خودش."""
    from app.models.psych_test import PsychAttempt, PsychTest

    limit = min(int(args.get("limit") or 8), 20)
    rows = db.execute(
        select(PsychAttempt, PsychTest)
        .join(PsychTest, PsychAttempt.test_id == PsychTest.id)
        .where(PsychAttempt.user_id == actor.id)
        .order_by(PsychAttempt.created_at.desc())
        .limit(limit)
    ).all()
    return {
        "count": len(rows),
        "results": [
            {
                "test_title": t.title,
                "score": int(a.score or 0),
                "interpretation": a.interpretation_label,
                "taken_at": a.created_at.strftime("%Y-%m-%d %H:%M") if a.created_at else None,
            }
            for a, t in rows
        ],
    }


def tool_my_file_summary(db: Session, actor: User, args: dict) -> dict:
    """خلاصهٔ پروندهٔ مشاورهٔ خودِ کاربر (شمار آزمون/مشاوره/نوبت + آخرین فعالیت)."""
    from app.services import counseling_file as cf

    data = cf.file_out(db, actor, limit=8)
    last = data["items"][:3]
    return {
        "file_code": data["file"]["file_code"],
        "counts": data["counts"],
        "last_activities": [
            {"kind": i["kind"], "title": i["title"], "at": i.get("at")}
            for i in last
        ],
    }


def tool_create_booking_request(db: Session, actor: User, args: dict) -> dict:
    """ثبت درخواست مشاوره از دل گفتگو (ابزار نوشتاری — فقط کارکنان).

    همان جریان «ثبت حضوری/تلفنی» پذیرش: درخواست جدید با ارجاع «دستیار هوشمند»
    ثبت می‌شود و پذیرش برای نوبت‌دهی تماس می‌گیرد. اسلات اشغال نمی‌شود.
    """
    import re

    from app.models.consultation import ConsultationRequest
    from app.services.audit import record_audit

    full_name = (args.get("full_name") or "").strip()
    mobile = (args.get("mobile") or "").strip()
    topic = (args.get("topic") or "").strip() or "مشاوره"
    message = (args.get("message") or "").strip()
    if len(full_name) < 3:
        return {"error": "نام و نام خانوادگی مراجع را کامل بدهید (حداقل ۳ حرف)"}
    norm = re.sub(r"[ \-()]", "", mobile)
    if norm.startswith("+98"):
        norm = "0" + norm[3:]
    elif norm.startswith("98") and len(norm) == 12:
        norm = "0" + norm[2:]
    if not re.fullmatch(r"09\d{9}", norm):
        return {"error": "شماره موبایل معتبر نیست (قالب 09xxxxxxxxx)"}
    r = ConsultationRequest(
        full_name=full_name[:200],
        mobile=norm,
        topic=topic[:100],
        message=message[:2000] or None,
        status="new",
        referral_source="assistant",
    )
    db.add(r)
    db.flush()
    record_audit(db, action="assistant.booking_request", actor_user_id=actor.id,
                 entity_type="consultation_request", entity_id=str(r.id),
                 detail={"mobile": norm})
    db.commit()
    return {
        "created": True,
        "request_id": str(r.id),
        "full_name": full_name,
        "topic": topic,
        "note": "درخواست ثبت شد؛ پذیرش برای هماهنگی نوبت تماس می‌گیرد. وضعیت در پنل «درخواست‌های مشاوره».",
    }


# ----------------------------------------------------------------- رجیستری
@dataclass
class ToolRegistry:
    """رجیستری ابزارها — الگوی ctx.tools در dsh؛ افزودن ابزار = ثبت ردیف جدید."""

    tools: dict[str, Tool] = field(default_factory=dict)

    def register(self, tool: Tool) -> None:
        self.tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self.tools.get(name)

    def catalog(self) -> list[dict]:
        """متادیتای عمومی برای UI (بدون جزئیات داخلی)."""
        return [
            {"name": t.name, "title": t.title, "description": t.description, "staff_only": t.staff_only}
            for t in self.tools.values()
        ]


def build_registry() -> ToolRegistry:
    """ساخت رجیستری پیش‌فرض فاز ۵۳."""
    reg = ToolRegistry()
    reg.register(Tool(
        name="search_services",
        title="جست‌وجوی خدمات",
        description="جست‌وجوی خدمات فعال سامانه با کلیدواژه (نام خدمت)",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "کلیدواژه نام خدمت"},
                "limit": {"type": "integer", "description": "حداکثر تعداد (پیش‌فرض ۸)"},
            },
            "required": [],
        },
        func=tool_search_services,
    ))
    reg.register(Tool(
        name="list_branches",
        title="فهرست شعب",
        description="شعب منتشرشده سامانه با فیلتر اختیاری شهر",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string", "description": "نام شهر برای فیلتر"}},
            "required": [],
        },
        func=tool_list_branches,
    ))
    reg.register(Tool(
        name="my_orders",
        title="سفارش‌های من",
        description="خلاصهٔ سفارش‌های اخیر خودِ کاربر (شماره، وضعیت، مبلغ)",
        parameters={
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "حداکثر تعداد (پیش‌فرض ۱۰)"}},
            "required": [],
        },
        func=tool_my_orders,
    ))
    reg.register(Tool(
        name="my_appointments",
        title="نوبت‌های من",
        description="نوبت‌های آیندهٔ خودِ کاربر",
        parameters={"type": "object", "properties": {}, "required": []},
        func=tool_my_appointments,
    ))
    reg.register(Tool(
        name="wallet_balance",
        title="مانده کیف پول",
        description="مانده کیف پول خودِ کاربر",
        parameters={"type": "object", "properties": {}, "required": []},
        func=tool_wallet_balance,
    ))
    reg.register(Tool(
        name="service_topics",
        title="دسته‌بندی خدمات",
        description="گروه‌بندی موضوعی خدمات فعال سامانه",
        parameters={"type": "object", "properties": {}, "required": []},
        func=tool_service_topics,
    ))
    reg.register(Tool(
        name="cases_summary",
        title="خلاصهٔ پرونده‌ها",
        description="تعداد پرونده‌ها بر اساس وضعیت (ابزار کارکنان؛ بدون محتوای بالینی)",
        parameters={"type": "object", "properties": {}, "required": []},
        func=tool_cases_summary,
        staff_only=True,
    ))
    reg.register(Tool(
        name="no_show_risk",
        title="ریسک عدم حضور",
        description="شمار نوبت‌های پرریسک عدم‌حضور در روزهای پیش‌رو (ابزار کارکنان)",
        parameters={
            "type": "object",
            "properties": {"days_ahead": {"type": "integer", "description": "افق روزها (پیش‌فرض ۷)"}},
            "required": [],
        },
        func=tool_no_show_risk,
        staff_only=True,
    ))
    reg.register(Tool(
        name="upcoming_appointments_staff",
        title="نوبت‌های پیش‌رو سامانه",
        description="نوبت‌های آیندهٔ کل سامانه برای برنامه‌ریزی پذیرش (ابزار کارکنان)",
        parameters={
            "type": "object",
            "properties": {"days_ahead": {"type": "integer", "description": "افق روزها (پیش‌فرض ۷)"}},
            "required": [],
        },
        func=tool_upcoming_appointments_staff,
        staff_only=True,
    ))
    # --- فاز ۷۰: همهٔ قابلیت‌ها در گفتگو ---
    reg.register(Tool(
        name="find_counselor",
        title="مشاوران قابل رزرو",
        description="فهرست مشاوران فعال با صلاحیت معتبر + لینک صفحهٔ رزرو هر مشاور",
        parameters={
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "حداکثر تعداد (پیش‌فرض ۵)"}},
            "required": [],
        },
        func=tool_find_counselor,
    ))
    reg.register(Tool(
        name="my_psych_results",
        title="نتایج آزمون‌های من",
        description="نتایج آزمون‌های روان‌شناسی خودِ کاربر (عنوان، نمره، تفسیر، زمان)",
        parameters={
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "حداکثر تعداد (پیش‌فرض ۸)"}},
            "required": [],
        },
        func=tool_my_psych_results,
    ))
    reg.register(Tool(
        name="my_file_summary",
        title="پروندهٔ مشاورهٔ من",
        description="خلاصهٔ پروندهٔ مشاورهٔ کاربر: شمارهٔ پرونده، شمار آزمون‌ها/مشاوره‌ها/نوبت‌ها و آخرین فعالیت‌ها",
        parameters={"type": "object", "properties": {}, "required": []},
        func=tool_my_file_summary,
    ))
    reg.register(Tool(
        name="create_booking_request",
        title="ثبت درخواست مشاوره",
        description="ثبت درخواست مشاوره برای مراجع (نام + موبایل + موضوع) — پذیرش تماس می‌گیرد (ابزار کارکنان؛ نوشتاری)",
        parameters={
            "type": "object",
            "properties": {
                "full_name": {"type": "string", "description": "نام و نام خانوادگی مراجع"},
                "mobile": {"type": "string", "description": "موبایل مراجع (09xxxxxxxxx)"},
                "topic": {"type": "string", "description": "موضوع مشاوره"},
                "message": {"type": "string", "description": "توضیح اختیاری"},
            },
            "required": ["full_name", "mobile"],
        },
        func=tool_create_booking_request,
        staff_only=True,
    ))
    return reg


def staff_allowed(user: User, tool: Tool) -> bool:
    """بررسی سیاست دسترسی ابزار — defense in depth (داخل اجرا هم چک می‌شود)."""
    if not tool.staff_only:
        return True
    return bool({r.code for r in user.roles}.intersection(set(tool.staff_roles)))
