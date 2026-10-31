"""خدمات رزرو آنلاین اسلات - فاز ۲۱

قرارداد زمانی سیستم (مانند بقیه ماژول‌ها): ساعت محلی ایران به‌صورت
naive در ستون timestamptz با آفست UTC ذخیره می‌شود؛ یعنی «09:00» ثبت‌شده
نماینده ساعت ۹ صبح محلی است. برای مقایسه «اکنون» آفست +03:30 اعمال می‌شود.

پیش‌فرض‌ها: شنبه تا چهارشنبه ۹-۱۷، پنجشنبه ۹-۱۳، جمعه تعطیل،
طول هر اسلات ۶۰ دقیقه، بازه قابل رزرو از فردا تا ۳۰ روز آینده.
"""
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment, AppointmentStatus
from app.models.consultation import ConsultPaymentStatus, ConsultationRequest
from app.core.config import get_settings

UTC = timezone.utc
WALL_OFFSET = timedelta(hours=3, minutes=30)  # آفست ثابت ایران (بدون ساعت تابستانی)

SLOT_MINUTES = 60
DAYS_AHEAD = 30

WORK_HOURS = {
    5: (time(9, 0), time(17, 0)),   # شنبه
    6: (time(9, 0), time(17, 0)),   # یکشنبه
    0: (time(9, 0), time(17, 0)),   # دوشنبه
    1: (time(9, 0), time(17, 0)),   # سه‌شنبه
    2: (time(9, 0), time(17, 0)),   # چهارشنبه
    3: (time(9, 0), time(13, 0)),   # پنجشنبه
}
CLOSED_WEEKDAYS = {4}  # جمعه


def _now_wall() -> datetime:
    """«اکنون» با قرارداد ذخیره‌سازی سیستم"""
    return datetime.now(UTC) + WALL_OFFSET


def _slot_starts(day: date) -> list[datetime]:
    if day.weekday() in CLOSED_WEEKDAYS:
        return []
    open_t, close_t = WORK_HOURS[day.weekday()]
    out: list[datetime] = []
    cur = datetime.combine(day, open_t, tzinfo=UTC)
    close = datetime.combine(day, close_t, tzinfo=UTC)
    while cur + timedelta(minutes=SLOT_MINUTES) <= close:
        out.append(cur)
        cur += timedelta(minutes=SLOT_MINUTES)
    return out


def bookable_range() -> tuple[date, date]:
    today = _now_wall().date()
    return today + timedelta(days=1), today + timedelta(days=DAYS_AHEAD)


def _busy_intervals(db: Session, counselor_id, from_day: date, to_day: date) -> list[tuple[datetime, datetime]]:
    start_dt = datetime.combine(from_day, time.min, tzinfo=UTC)
    end_dt = datetime.combine(to_day + timedelta(days=1), time.min, tzinfo=UTC)

    out: list[tuple[datetime, datetime]] = []
    rows = db.scalars(
        select(Appointment).where(
            Appointment.counselor_id == counselor_id,
            Appointment.status == AppointmentStatus.SCHEDULED,
            Appointment.scheduled_at >= start_dt,
            Appointment.scheduled_at < end_dt,
        )
    ).all()
    for a in rows:
        dur = a.duration_minutes or SLOT_MINUTES
        s = a.scheduled_at
        if s.tzinfo is None:
            s = s.replace(tzinfo=UTC)
        out.append((s, s + timedelta(minutes=dur)))

    # فاز ۶۹: رزرو در انتظار پرداخت آنلاین فقط تا سقف TTL اسلات را اشغال
    # می‌کند؛ پس از آن (پرداخت‌نشده) اسلات آزاد اعلام می‌شود تا رزرو رهاشده
    # در درگاه، تقویم را برای همیشه ببندد. رزرو پرداخت‌شده یا بدون پرداخت
    # آنلاین (جریان قدیمی) همیشه اشغال است.
    # توجه: created_at با server_default=now() ذخیره می‌شود (UTC واقعی)،
    # پس مقایسه هم با UTC واقعی انجام می‌شود نه قرارداد ساعت محلی.
    unpaid_ttl = timedelta(minutes=get_settings().booking_unpaid_ttl_minutes)
    stale_cutoff = datetime.now(UTC) - unpaid_ttl
    pending = db.scalars(
        select(ConsultationRequest).where(
            ConsultationRequest.preferred_counselor_id == counselor_id,
            ConsultationRequest.status.in_(("new", "in_review")),
            ConsultationRequest.preferred_start_at.is_not(None),
            ConsultationRequest.preferred_start_at >= start_dt,
            ConsultationRequest.preferred_start_at < end_dt,
        )
    ).all()
    for r in pending:
        if r.payment_status == ConsultPaymentStatus.FAILED:
            continue  # پرداخت در درگاه تأیید نشد → اسلات دوباره آزاد است
        if r.payment_status == ConsultPaymentStatus.PENDING:
            created = r.created_at
            if created is not None:
                if created.tzinfo is None:
                    created = created.replace(tzinfo=UTC)
                if created < stale_cutoff:
                    continue  # منتظر پرداخت منقضی‌شده → اسلات آزاد
        s = r.preferred_start_at
        if s.tzinfo is None:
            s = s.replace(tzinfo=UTC)
        out.append((s, s + timedelta(minutes=SLOT_MINUTES)))

    # فاز ۲۶ - B09: اسلات‌های نگه‌داشت‌شده (hold فعال) هم اشغال محسوب می‌شوند
    from app.services.booking_hold import active_hold_intervals
    out.extend(active_hold_intervals(db, counselor_id, from_day, to_day))
    return out


def free_slots(db: Session, counselor_id, from_day: date, to_day: date) -> list[dict]:
    """لیست روزها و اسلات‌های آزاد مشاور در بازه داده‌شده"""
    if (to_day - from_day).days > 31:
        to_day = from_day + timedelta(days=31)
    busy = _busy_intervals(db, counselor_id, from_day, to_day)
    now = _now_wall()
    days: list[dict] = []
    day = from_day
    while day <= to_day:
        slots = []
        for s in _slot_starts(day):
            if s <= now:
                continue
            s_end = s + timedelta(minutes=SLOT_MINUTES)
            if any(s < e and b < s_end for b, e in busy):
                continue
            slots.append({"start_at": s.isoformat(), "label": s.strftime("%H:%M")})
        if slots:
            days.append({"date": day.isoformat(), "slots": slots})
        day += timedelta(days=1)
    return days


def validate_slot(db: Session, counselor_id, raw: datetime) -> datetime | None:
    """اعتبارسنجی اسلات انتخاب کاربر؛ نامعتبر/اشغال/خارج بازه => None"""
    if raw.tzinfo is None:
        raw = raw.replace(tzinfo=UTC)
    s = raw
    day = s.date()
    if day.weekday() in CLOSED_WEEKDAYS:
        return None
    if all(x != s for x in _slot_starts(day)):
        return None
    f, t = bookable_range()
    if not (f <= day <= t):
        return None
    busy = _busy_intervals(db, counselor_id, day - timedelta(days=1), day + timedelta(days=1))
    s_end = s + timedelta(minutes=SLOT_MINUTES)
    if any(s < e and b < s_end for b, e in busy):
        return None
    return s

def release_stale_unpaid_requests(db: Session) -> int:
    """فاز ۶۹ - آزادسازی رزروهای در انتظار پرداختِ منقضی.

    رزروی که payment_status='pending' و پرداخت آن تا سقف TTL
    (BOOKING_UNPAID_TTL_MINUTES) تأیید نشد «archived» می‌شود تا:
    ۱) ایندکس یکتای جزئی اسلات آزاد شود (کاربر دیگری بتواند همان اسلات را رزرو کند)؛
    ۲) درخواست برای پیگیری پذیرش حفظ شود (پاک نمی‌شود).
    در create_booking_hold و submit_consultation فراخوانی می‌شود.
    """
    cutoff = datetime.now(UTC) - timedelta(
        minutes=get_settings().booking_unpaid_ttl_minutes
    )
    rows = db.scalars(
        select(ConsultationRequest).where(
            ConsultationRequest.payment_status == ConsultPaymentStatus.PENDING,
            ConsultationRequest.status.in_(("new", "in_review")),
            ConsultationRequest.created_at < cutoff,
        )
    ).all()
    if not rows:
        return 0
    for r in rows:
        r.status = "archived"
    db.commit()
    return len(rows)
