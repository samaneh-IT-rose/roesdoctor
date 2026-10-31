"""فاز ۵۳ - حلقهٔ عامل Rosepsy (الگوی Agent Turn/Step Lifecycle سند dsh).

جریان یک Turn:
    پیام کاربر
      → نشست (system + تاریخچه + پیام جدید)
        → مدل (با شِمای ابزارهای مجاز همان کاربر)
          ← tool_calls؟ → اجرای امن ابزار → append پیام tool → دوباره مدل
          ← پیام نهایی → ثبت در نشست → پاسخ به UI
- سقف گام (AI_AGENT_MAX_STEPS، پیش‌فرض ۴) مثل dsh جلوی حلقهٔ بی‌پایان را می‌گیرد؛
- fail-soft: نبود کلید/خطای مدل/هر استثنا → پاسخ‌دهندهٔ قاعده‌محور — از فاز ۷۰
  «اقدام‌محور»: نیت کاربر → اجرای واقعی ابزارها → پاسخ با دادهٔ واقعی DB؛
- مرز داده: ابزارها فقط خودِ کاربر یا دادهٔ عمومی؛ ابزار کارکنان فقط با نقش؛
- دیسکلیمر ثابت فاز ۳۵ روی پاسخ نهایی می‌ماند.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.agent import AgentMessage, AgentSession
from app.models.user import User
from app.services.agent import provider
from app.services.agent.tools import ToolRegistry, build_registry, staff_allowed
from app.services.ai_assistant import _DISCLAIMER, _rule_answer  # بازاستفاده از هستهٔ فاز ۳۵

SYSTEM_PROMPT = (
    "تو «دستیار هوشمند Rosepsy» هستی؛ دستیار سامانهٔ مدیریت مراکز مشاوره و آزمون‌های روان‌شناسی. "
    "همیشه فارسی و کوتاه و دقیق پاسخ بده. "
    "برای اطلاع از خدمات، شعب، سفارش‌ها، نوبت‌ها، کیف پول و آمار عملیاتی از ابزارهای در دسترس استفاده کن "
    "و پیش از پاسخ نهایی، دادهٔ ابزار را با اعداد واقعی بازگو کن؛ عددی از خودت نساز. "
    "پاسخ تو فقط دربارهٔ اطلاعات عمومی سامانه است؛ تشخیص یا درمان بالینی ارائه نکن و "
    "در موارد بالینی کاربر را به مشاور حرفه‌ای ارجاع بده. "
    "اگر ابزار پاسخ لازم را نداد، صادقانه بگو موضوع خارج از دامنهٔ توست."
)


@dataclass
class StepTrace:
    """رد یک گام ابزار برای UI و لاگ (بدون کلید، بدون دادهٔ بالینی)."""

    tool_name: str
    tool_title: str
    args: dict
    result: dict


@dataclass
class AgentTurnResult:
    response: str
    provider: str
    disclaimer: str
    latency_ms: int
    steps: list[StepTrace] = field(default_factory=list)
    fallback_used: bool = False


def _openai_tools(reg: ToolRegistry, actor: User) -> list[dict]:
    """شِمای ابزارهای مجاز برای همان کاربر (ابزار کارکنان فقط با نقش)."""
    out = []
    for t in reg.tools.values():
        if not staff_allowed(actor, t):
            continue
        out.append({
            "type": "function",
            "function": {
                "name": t.name,
                "description": f"{t.title}: {t.description}",
                "parameters": t.parameters,
            },
        })
    return out


def _history_messages(db: Session, session_id: uuid.UUID, limit: int = 20) -> list[dict]:
    """بازپخش نشست (Session Replay — الگوی dsh): آخرین پیام‌ها به ترتیب زمانی."""
    rows = (
        db.query(AgentMessage)
        .filter(AgentMessage.session_id == session_id)
        .order_by(AgentMessage.created_at.desc(), AgentMessage.id.desc())
        .limit(limit)
        .all()
    )
    rows.reverse()
    msgs: list[dict] = []
    for r in rows:
        if r.role == "user":
            msgs.append({"role": "user", "content": r.content or ""})
        elif r.role == "assistant":
            msgs.append({"role": "assistant", "content": r.content or ""})
        # پیام‌های tool در بازپخش ساده حذف می‌شوند (مدل وضعیت را از پاسخ نهایی می‌فهمد)
    return msgs


def _run_tool(db: Session, actor: User, reg: ToolRegistry, name: str, raw_args: str) -> tuple[dict, StepTrace | None]:
    """اجرای امن یک ابزار؛ خطا → دیکشنری خطا (هیچ استثنایی به بیرون نمی‌رود)."""
    tool = reg.get(name)
    if tool is None:
        return {"error": "ابزار شناخته‌شده نیست"}, None
    if not staff_allowed(actor, tool):
        return {"error": "دسترسی به این ابزار برای نقش شما مجاز نیست"}, None
    try:
        args = json.loads(raw_args or "{}")
        if not isinstance(args, dict):
            args = {}
    except ValueError:
        args = {}
    try:
        result = tool.func(db, actor, args)
    except Exception:  # noqa: BLE001 — خطای ابزار هرگز Turn را نمی‌شکند
        result = {"error": "اجرای ابزار ناموفق بود"}
    trace = StepTrace(tool_name=tool.name, tool_title=tool.title, args=args, result=result)
    return result, trace


def _tool_result_text(result: dict) -> str:
    """فشرده‌سازی خروجی ابزار برای مدل (متن کوتاه فارسی/JSON)."""
    try:
        return json.dumps(result, ensure_ascii=False)[:1500]
    except (TypeError, ValueError):
        return "{}"


# ---------------------------------------------------------------------------
# فاز ۷۰ - پاسخ‌دهندهٔ «اقدام‌محور» بدون LLM: نیت → اجرای ابزار واقعی → متن
# (پیش از این بدون کلید LLM فقط متن ثابت برمی‌گشت و کاربر هیچ قابلیتی در
# گفتگو نداشت؛ حالا همان ابزارهای عامل در حالت قاعده‌محور هم اجرا می‌شوند.)
_BOOKING_WORDS = ("نوبت", "رزرو", "appointment", "booking")
_BOOKING_MINE = ("نوبت‌های من", "نوبت های من", "نوبتام", "وقت‌های من")
_RESULT_WORDS = ("نتیجه", "نتایج", "آزمون", "ازمون", "نمره", "امتیاز آزمون", "test")
_FILE_WORDS = ("پروندهٔ مشاوره", "پرونده مشاوره", "تاریخچه", "سوابق", "پرونده‌ام")
_ORDER_WORDS = ("سفارش", "پرداخت", "فاکتور", "خرید")
_WALLET_WORDS = ("کیف پول", "کیف‌پول", "مانده", "اعتبار")
_BRANCH_WORDS = ("شعبه", "آدرس", "مرکز", "کجا")
_SERVICE_WORDS = ("خدمت", "خدمات", "درمان", "کارگاه", "دوره")
_CASES_WORDS = ("پرونده‌ها", "آمار پرونده", "خلاصهٔ پرونده")
_GREETING_WORDS = ("سلام", "درود", "خسته نباشید", "وقت بخیر")
_THANKS_WORDS = ("ممنون", "مرسی", "سپاس", "متشکر")


def _fmt_results(result: dict) -> str:
    rows = result.get("results") or []
    if not rows:
        return "هنوز آزمونی انجام نداده‌اید؛ از «مرکز آزمون روان‌شناسی» می‌توانید شروع کنید."
    lines = [f"{len(rows)} نتیجهٔ اخیر شما:"]
    for r in rows:
        lines.append(
            f"• {r['test_title']} — نمره {r['score']} ({r['interpretation']}) — {r['taken_at'] or ''}".rstrip(" —")
        )
    lines.append("گزارش کامل هر آزمون در «مرکز آزمون روان‌شناسی → نتایج من» است.")
    return "\n".join(lines)


def _fmt_counselors(result: dict) -> str:
    rows = result.get("counselors") or []
    url = result.get("booking_url") or "/booking"
    if not rows:
        return (
            "در حال حاضر مشاوری برای رزرو فعال نیست. "
            "می‌توانید درخواست مشاوره ثبت کنید تا پذیرش با شما تماس بگیرد."
        )
    lines = ["مشاوران قابل رزرو (به‌ترتیب امتیاز):"]
    for c in rows:
        spec = f" ({c['specialty']})" if c.get("specialty") else ""
        lines.append(f"• {c['name']}{spec} — رزرو: {c['profile_url']}")
    lines.append(f"صفحهٔ رزرو نوبت: {url} — انتخاب زمان، پرداخت آنلاین و ثبت نهایی همه آنلاین است.")
    return "\n".join(lines)


def _fmt_file(result: dict) -> str:
    counts = result.get("counts") or {}
    kind_fa = {"psych_test": "آزمون", "consultation": "مشاوره", "appointment": "نوبت"}
    lines = [
        f"پروندهٔ مشاورهٔ شما ({result.get('file_code', '')}): "
        f"{counts.get('psych_tests', 0)} آزمون، {counts.get('consultations', 0)} درخواست/رزرو مشاوره، "
        f"{counts.get('appointments', 0)} نوبت."
    ]
    for i in result.get("last_activities") or []:
        at = (i.get("at") or "")[:16].replace("T", " ")
        lines.append(f"• {kind_fa.get(i.get('kind'), i.get('kind'))}: {i.get('title')} — {at}")
    lines.append("شرح کامل تاریخچه در «پنل شخصی → پروندهٔ مشاوره من» است.")
    return "\n".join(lines)


def _rule_action_answer(
    db: Session, actor: User, message: str, reg: ToolRegistry
) -> tuple[str, list[StepTrace]]:
    """نیت‌یابی قاعده‌محور → اجرای ابزار واقعی → پاسخ فارسی با دادهٔ واقعی."""
    text = (message or "").strip().lower()
    steps: list[StepTrace] = []

    def run(name: str, args: dict | None = None) -> dict:
        result, trace = _run_tool(db, actor, reg, name, json.dumps(args or {}, ensure_ascii=False))
        if trace is not None:
            steps.append(trace)
        return result

    def can(name: str) -> bool:
        tool = reg.get(name)
        return tool is not None and staff_allowed(actor, tool)

    # «ثبت درخواست مشاوره برای نام ۰۹…» — الگوی صریح ثبت از پذیرش/کارکنان
    m = re.search(r"09\d{9}", text.replace("۰", "0").replace("۹", "9"))
    if m and ("ثبت" in text or "درخواست" in text) and can("create_booking_request"):
        name_part = re.sub(r"09\d{9}", "", text)
        name_part = re.sub(r"(ثبت|درخواست|مشاوره|برای|لطفا|کنید|کن)", " ", name_part).strip()
        result = run("create_booking_request", {
            "full_name": name_part or message[:60], "mobile": m.group(0),
            "topic": "مشاوره (ثبت از گفتگو)",
        })
        if "error" not in result:
            return f"✅ {result.get('note', 'درخواست ثبت شد.')}", steps
        return f"{result.get('error')} — مثال: «ثبت درخواست مشاوره برای علی احمدی 09121234567».", steps

    if any(w in text for w in _BOOKING_MINE):
        result = run("my_appointments")
        rows = result.get("appointments") or []
        if not rows:
            return "نوبت آینده‌ای ندارید. برای رزرو نوبت جدید بگویید «می‌خواهم نوبت رزرو کنم».", steps
        lines = [f"{len(rows)} نوبت آیندهٔ شما:"]
        lines += [f"• {r.get('scheduled_at','')} — {r.get('service_title') or r.get('status','')}" for r in rows]
        return "\n".join(lines), steps

    if any(w in text for w in _BOOKING_WORDS):
        result = run("find_counselor")
        body = _fmt_counselors(result)
        if can("create_booking_request"):
            body += ("\nبرای ثبت درخواست مراجع از همین‌جا، بنویسید: "
                     "«ثبت درخواست مشاوره برای نام مراجع 09xxxxxxxxx».")
        return body, steps

    if any(w in text for w in _RESULT_WORDS):
        return _fmt_results(run("my_psych_results")), steps

    if any(w in text for w in _FILE_WORDS):
        return _fmt_file(run("my_file_summary")), steps

    if any(w in text for w in _ORDER_WORDS):
        result = run("my_orders")
        rows = result.get("orders") or []
        if not rows:
            return "سفارشی برای شما ثبت نشده است.", steps
        lines = [f"{len(rows)} سفارش اخیر شما:"]
        lines += [f"• {r.get('order_number','')} — {r.get('status','')} — {r.get('amount','')}" for r in rows]
        return "\n".join(lines), steps

    if any(w in text for w in _WALLET_WORDS):
        result = run("wallet_balance")
        return f"مانده کیف پول شما: {result.get('balance', result)}", steps

    if any(w in text for w in _BRANCH_WORDS):
        result = run("list_branches")
        rows = result.get("branches") or []
        if not rows:
            return "شعبه‌ای یافت نشد.", steps
        lines = [f"{len(rows)} شعبه:"]
        lines += [f"• {r.get('name','')} ({r.get('city','')}) — {r.get('address','')}" for r in rows]
        return "\n".join(lines), steps

    if any(w in text for w in _SERVICE_WORDS):
        result = run("search_services")
        rows = result.get("services") or []
        if not rows:
            return "خدمت فعالی یافت نشد.", steps
        lines = [f"{len(rows)} خدمت فعال:"]
        lines += [f"• {r.get('title','')}" for r in rows]
        return "\n".join(lines), steps

    if any(w in text for w in _CASES_WORDS) and can("cases_summary"):
        result = run("cases_summary")
        return f"خلاصهٔ پرونده‌ها: {json.dumps(result, ensure_ascii=False)}", steps

    if any(w in text for w in _GREETING_WORDS):
        return (
            "سلام! من دستیار هوشمند Rosepsy هستم و بدون نیاز به تنظیم اضافه کار می‌کنم. "
            "می‌توانید بپرسید: «می‌خواهم نوبت رزرو کنم»، «نتایج آزمون‌هام را بگو»، "
            "«پروندهٔ مشاورهٔ من»، «سفارش‌های من»، «مانده کیف پول» یا «شعب تهران»."
        ), steps

    if any(w in text for w in _THANKS_WORDS):
        return "خواهش می‌کنم! اگر چیز دیگری لازم داشتید در خدمتم.", steps

    return _rule_answer(message), steps


def run_turn(
    db: Session,
    actor: User,
    session: AgentSession,
    message: str,
    registry: ToolRegistry | None = None,
) -> AgentTurnResult:
    """یک Turn کامل حلقهٔ عامل + ثبت ماندگار در نشست (append-only)."""
    started = time.monotonic()
    reg = registry or build_registry()
    steps: list[StepTrace] = []
    provider_name = "rule"
    fallback = False
    final_answer: str | None = None

    db.add(AgentMessage(session_id=session.id, role="user", content=(message or "")[:2000]))
    db.commit()

    if provider.is_enabled():
        try:
            from app.core.config import get_settings
            max_steps = min(int(getattr(get_settings(), "ai_agent_max_steps", 4) or 4), 8)
        except Exception:  # noqa: BLE001
            max_steps = 4

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages += _history_messages(db, session.id, limit=18)
        messages.append({"role": "user", "content": (message or "")[:2000]})
        openai_tools = _openai_tools(reg, actor)

        for _step_index in range(max_steps):
            result = provider.chat_completion(messages, tools=openai_tools or None)
            if result is None:
                fallback = True
                break
            provider_name = "llm"
            if result.tool_calls:
                messages.append({
                    "role": "assistant",
                    "content": result.content or "",
                    "tool_calls": result.tool_calls,
                })
                for tc in result.tool_calls:
                    fn = (tc.get("function") or {}) if isinstance(tc, dict) else {}
                    name = fn.get("name") or ""
                    raw_args = fn.get("arguments") or "{}"
                    tool_result, trace = _run_tool(db, actor, reg, name, raw_args)
                    if trace is not None:
                        steps.append(trace)
                        db.add(AgentMessage(
                            session_id=session.id,
                            role="tool",
                            content=_tool_result_text(tool_result),
                            tool_name=trace.tool_name,
                            tool_args=trace.args,
                            tool_result=trace.result,
                        ))
                    messages.append({
                        "role": "tool",
                        "tool_call_id": (tc.get("id") if isinstance(tc, dict) else None) or "",
                        "content": _tool_result_text(tool_result),
                    })
                db.commit()
                continue  # گام بعدی: مدل با نتایج ابزار
            # پاسخ نهایی متنی
            final_answer = (result.content or "").strip() or None
            break
        else:
            # سقف گام پر شد — از مدل خواسته می‌شود جمع‌بندی کند؛ اگر نشد fallback
            result = provider.chat_completion(messages + [{
                "role": "user",
                "content": "خلاصهٔ کوتاه نهایی را همین حالا بدون ابزار جدید بده.",
            }])
            if result is not None and (result.content or "").strip():
                final_answer = result.content.strip()
            else:
                fallback = True
    else:
        fallback = True

    if final_answer is None:
        provider_name = "rule" if fallback else provider_name
        # فاز ۷۰ - پاسخ اقدام‌محور: نیت → ابزار واقعی → متن با دادهٔ واقعی
        final_answer, rule_steps = _rule_action_answer(db, actor, message, reg)
        for trace in rule_steps:
            steps.append(trace)
            db.add(AgentMessage(
                session_id=session.id,
                role="tool",
                content=_tool_result_text(trace.result),
                tool_name=trace.tool_name,
                tool_args=trace.args,
                tool_result=trace.result,
            ))

    latency = int((time.monotonic() - started) * 1000)
    db.add(AgentMessage(
        session_id=session.id,
        role="assistant",
        content=final_answer[:4000],
        provider=provider_name,
        latency_ms=latency,
    ))
    db.commit()

    return AgentTurnResult(
        response=final_answer,
        provider=provider_name,
        disclaimer=_DISCLAIMER,
        latency_ms=latency,
        steps=steps,
        fallback_used=fallback and provider_name == "rule",
    )
