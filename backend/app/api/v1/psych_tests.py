"""فاز ۳۵ - B37 سند جامع: تست روان‌شناسی و تفسیر — تصمیم D08 (ناظر علمی).

قواعد پذیرش:
- ساخت/ویرایش ابزار، سؤال و بازه تفسیر: مدیر (SYSTEM_ADMIN/ORG_MANAGER)؛
- «انتشار ابزار علمی فقط با تأیید ناظر علمی»: draft → pending_review
  (ارسال برای بازبینی توسط مدیر) → published | rejected — فقط نقش
  TECHNICAL_SUPERVISOR می‌تواند review کند (مدیر ۴۰۳)؛ بازرسی با
  یادداشت و هویت ناظر ثبت می‌شود؛
- تأیید ابزار بدون سؤال یا بدون حداقل یک بازه تفسیر ممنوع (۴۲۲)؛
  ویرایش ابزار منتشرشده → بازگشت به draft (نسخه علمی باید دوباره
  تأیید شود)؛
- برگزاری فقط ابزار منتشرشده؛ پاسخ‌ها اندیس گزینه‌اند؛ نمره = جمع
  امتیاز گزینه‌ها؛ تفسیر از بازه‌های ثبت‌شده (اولین بازه شامل نمره)؛
  نتیجه snapshot می‌شود؛ فهرست عمومی فقط منتشرشده‌ها.
"""
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.models.psych_test import (
    PsychAttempt,
    PsychInterpretation,
    PsychQuestion,
    PsychStatus,
    PsychTest,
)
from app.models.topics import Topic
from app.models.user import User
from app.services.psych_report import build_report_payload

router = APIRouter(tags=["psych-tests"])

MANAGE_ROLES = ("SYSTEM_ADMIN", "ORG_MANAGER")
VIEW_ROLES = (*MANAGE_ROLES, "TECHNICAL_SUPERVISOR", "RECEPTION", "COUNSELOR")
REVIEWER_ROLES = ("TECHNICAL_SUPERVISOR",)  # D08: ناظر علمی

_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,118}[a-z0-9])?$")


def _validate_slug(slug: str) -> str:
    s = slug.strip().lower()
    if not _SLUG_RE.match(s):
        raise HTTPException(
            status_code=422, detail="slug فقط حروف کوچک لاتین، عدد و خط تیره است"
        )
    return s


def _test_out(db: Session, t: PsychTest, *, with_counts: bool = True) -> dict:
    topic = db.get(Topic, t.topic_id) if t.topic_id else None
    reviewer = db.get(User, t.reviewed_by) if t.reviewed_by else None
    out = {
        "id": str(t.id),
        "slug": t.slug,
        "title": t.title,
        "description": t.description,
        "topic_id": str(t.topic_id) if t.topic_id else None,
        "topic_name": topic.name if topic else None,
        # فاز ۵۰ - متادیتای کاتالوگ
        "code": t.code,
        "age_range": t.age_range,
        "estimated_minutes": t.estimated_minutes,
        "accent_color": t.accent_color,
        "sort_order": t.sort_order,
        "status": t.status,
        "review_note": t.review_note,
        "reviewed_by": reviewer.display_name if reviewer else None,
        "reviewed_at": t.reviewed_at.isoformat() if t.reviewed_at else None,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }
    if with_counts:
        out["question_count"] = int(
            db.scalar(select(func.count()).select_from(PsychQuestion).where(PsychQuestion.test_id == t.id)) or 0
        )
        out["interpretation_count"] = int(
            db.scalar(select(func.count()).select_from(PsychInterpretation).where(PsychInterpretation.test_id == t.id)) or 0
        )
        out["attempt_count"] = int(
            db.scalar(select(func.count()).select_from(PsychAttempt).where(PsychAttempt.test_id == t.id)) or 0
        )
    return out


def _question_out(q: PsychQuestion) -> dict:
    return {
        "id": str(q.id),
        "test_id": str(q.test_id),
        "prompt": q.prompt,
        "options": q.options or [],
        "subscale": q.subscale,
        # فاز ۵۰ - عکس پیوست سؤال (URL آماده)
        "image_url": f"/api/v1/public/psych-images/{q.image_path}" if q.image_path else None,
        "sort_order": q.sort_order,
    }


def _interp_out(i: PsychInterpretation) -> dict:
    return {
        "id": str(i.id),
        "test_id": str(i.test_id),
        "score_min": i.score_min,
        "score_max": i.score_max,
        "label": i.label,
        "guidance": i.guidance,
        "sort_order": i.sort_order,
    }


def _attempt_out(a: PsychAttempt) -> dict:
    return {
        "id": str(a.id),
        "test_id": str(a.test_id),
        "user_id": str(a.user_id),
        "score": int(a.score or 0),
        "interpretation_label": a.interpretation_label,
        "interpretation_guidance": a.interpretation_guidance,
        "subscale_scores": a.subscale_scores,
        "demographics": a.demographics,
        # فاز ۶۳ - گزارش تحلیلی چندلایه (snapshot)
        "result_payload": a.result_payload,
        # فاز ۷۰ - نتیجهٔ دیده‌شده + پروندهٔ متصل
        "viewed_at": a.viewed_at.isoformat() if a.viewed_at else None,
        "case_id": str(a.case_id) if a.case_id else None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


# ---------------------------------------------------------------- schemas
class PsychTestCreate(BaseModel):
    slug: str = Field(min_length=2, max_length=120)
    title: str = Field(min_length=2, max_length=300)
    description: str | None = Field(default=None, max_length=20_000)
    topic_id: uuid.UUID | None = None


class PsychTestUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=300)
    description: str | None = Field(default=None, max_length=20_000)
    topic_id: uuid.UUID | None = None


class PsychReviewAction(BaseModel):
    approve: bool
    note: str | None = Field(default=None, max_length=1000)


class QuestionCreate(BaseModel):
    prompt: str = Field(min_length=3, max_length=1000)
    options: list[dict] = Field(min_length=2, max_length=10)  # [{"label","score"}]
    subscale: str | None = Field(default=None, max_length=100)
    sort_order: int = Field(default=0, ge=0)


class InterpretationCreate(BaseModel):
    score_min: int = Field(ge=0)
    score_max: int = Field(ge=0)
    label: str = Field(min_length=2, max_length=200)
    guidance: str | None = Field(default=None, max_length=1000)
    sort_order: int = Field(default=0, ge=0)


class AttemptCreate(BaseModel):
    answers: list[int] = Field(min_length=1)
    # فاز ۵۰ - مشخصات اولیه (فرم مرجع): کلیدهای gender/age/education/marital
    demographics: dict | None = None


# ---------------------------------------------------------------- admin
@router.get("/psych-tests")
def list_tests(
    include_unpublished: bool = Query(default=True),
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*VIEW_ROLES)),
) -> dict:
    q = select(PsychTest).order_by(PsychTest.created_at.desc()).limit(200)
    if not include_unpublished:
        q = q.where(PsychTest.status == PsychStatus.PUBLISHED)
    return {"items": [_test_out(db, t) for t in db.scalars(q).all()]}


@router.post("/psych-tests", status_code=201)
def create_test(
    payload: PsychTestCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    slug = _validate_slug(payload.slug)
    if db.scalars(select(PsychTest.id).where(PsychTest.slug == slug)).first() is not None:
        raise HTTPException(status_code=409, detail="این slug قبلاً استفاده شده است")
    if payload.topic_id is not None and db.get(Topic, payload.topic_id) is None:
        raise HTTPException(status_code=404, detail="دسته موضوعی یافت نشد")
    t = PsychTest(
        slug=slug,
        title=payload.title.strip(),
        description=payload.description,
        topic_id=payload.topic_id,
        status=PsychStatus.DRAFT,
        created_by=actor.id,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return _test_out(db, t)


@router.patch("/psych-tests/{test_id}")
def update_test(
    test_id: uuid.UUID,
    payload: PsychTestUpdate,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    t = db.get(PsychTest, test_id)
    if t is None:
        raise HTTPException(status_code=404, detail="ابزار یافت نشد")
    if payload.title is not None:
        t.title = payload.title.strip()
    if payload.description is not None:
        t.description = payload.description
    if payload.topic_id is not None:
        if db.get(Topic, payload.topic_id) is None:
            raise HTTPException(status_code=404, detail="دسته موضوعی یافت نشد")
        t.topic_id = payload.topic_id
    # ویرایش محتوای علمی منتشرشده → بازگشت به پیش‌نویس (D08: دوباره باید تأیید شود)
    if t.status == PsychStatus.PUBLISHED:
        t.status = PsychStatus.DRAFT
        t.review_note = None
        t.reviewed_by = None
        t.reviewed_at = None
    db.commit()
    db.refresh(t)
    return _test_out(db, t)


@router.post("/psych-tests/{test_id}/submit-review")
def submit_for_review(
    test_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    """ارسال برای بازبینی ناظر علمی (D08) — از draft یا rejected."""
    t = db.get(PsychTest, test_id)
    if t is None:
        raise HTTPException(status_code=404, detail="ابزار یافت نشد")
    if t.status not in (PsychStatus.DRAFT, PsychStatus.REJECTED):
        raise HTTPException(
            status_code=409, detail="فقط ابزار پیش‌نویس یا رد‌شده قابل ارسال برای بازبینی است"
        )
    questions = db.scalar(
        select(func.count()).select_from(PsychQuestion).where(PsychQuestion.test_id == test_id)
    ) or 0
    if int(questions) == 0:
        raise HTTPException(status_code=422, detail="ابزار بدون سؤال قابل ارسال برای بازبینی نیست")
    ranges = db.scalar(
        select(func.count()).select_from(PsychInterpretation).where(PsychInterpretation.test_id == test_id)
    ) or 0
    if int(ranges) == 0:
        raise HTTPException(status_code=422, detail="ابزار بدون بازه تفسیر قابل ارسال برای بازبینی نیست")
    t.status = PsychStatus.PENDING_REVIEW
    db.commit()
    db.refresh(t)
    return _test_out(db, t)


@router.post("/psych-tests/{test_id}/review")
def review_test(
    test_id: uuid.UUID,
    payload: PsychReviewAction,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*REVIEWER_ROLES)),
) -> dict:
    """تصمیم ناظر علمی (D08): تأیید → published؛ رد → rejected با یادداشت."""
    t = db.get(PsychTest, test_id)
    if t is None:
        raise HTTPException(status_code=404, detail="ابزار یافت نشد")
    if t.status != PsychStatus.PENDING_REVIEW:
        raise HTTPException(status_code=409, detail="این ابزار در انتظار بازبینی نیست")
    if payload.approve:
        ranges = db.scalar(
            select(func.count()).select_from(PsychInterpretation).where(PsychInterpretation.test_id == test_id)
        ) or 0
        if int(ranges) == 0:
            raise HTTPException(status_code=422, detail="تأیید ابزار بدون بازه تفسیر ممنوع است")
        t.status = PsychStatus.PUBLISHED
    else:
        if not payload.note:
            raise HTTPException(status_code=422, detail="رد ابزار نیازمند یادداشت ناظر علمی است")
        t.status = PsychStatus.REJECTED
    t.review_note = payload.note
    t.reviewed_by = actor.id
    t.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(t)
    return _test_out(db, t)


@router.post("/psych-tests/{test_id}/questions", status_code=201)
def add_question(
    test_id: uuid.UUID,
    payload: QuestionCreate,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    t = db.get(PsychTest, test_id)
    if t is None:
        raise HTTPException(status_code=404, detail="ابزار یافت نشد")
    clean: list[dict] = []
    for idx, opt in enumerate(payload.options):
        label = str(opt.get("label", "")).strip()
        score = opt.get("score", 0)
        if not label:
            raise HTTPException(status_code=422, detail=f"برچسب گزینه {idx + 1} الزامی است")
        try:
            score = int(score)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail=f"امتیاز گزینه {idx + 1} باید عدد باشد")
        if score < 0:
            raise HTTPException(status_code=422, detail=f"امتیاز گزینه {idx + 1} نمی‌تواند منفی باشد")
        clean.append({"label": label, "score": score})
    q = PsychQuestion(test_id=test_id, prompt=payload.prompt.strip(), options=clean,
                      subscale=(payload.subscale or None) and payload.subscale.strip() or None,
                      sort_order=payload.sort_order)
    db.add(q)
    if t.status == PsychStatus.PUBLISHED:
        t.status = PsychStatus.DRAFT
        t.review_note = None
        t.reviewed_by = None
        t.reviewed_at = None
    db.commit()
    db.refresh(q)
    return _question_out(q)


@router.delete("/psych-tests/{test_id}/questions/{question_id}", status_code=204)
def delete_question(
    test_id: uuid.UUID,
    question_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> None:
    q = db.get(PsychQuestion, question_id)
    if q is None or q.test_id != test_id:
        raise HTTPException(status_code=404, detail="سؤال یافت نشد")
    db.delete(q)
    t = db.get(PsychTest, test_id)
    if t and t.status == PsychStatus.PUBLISHED:
        t.status = PsychStatus.DRAFT
        t.review_note = None
        t.reviewed_by = None
        t.reviewed_at = None
    db.commit()


@router.get("/psych-tests/{test_id}/questions")
def list_questions(
    test_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*VIEW_ROLES)),
) -> dict:
    rows = db.scalars(
        select(PsychQuestion).where(PsychQuestion.test_id == test_id).order_by(PsychQuestion.sort_order)
    ).all()
    return {"items": [_question_out(q) for q in rows]}


@router.post("/psych-tests/{test_id}/interpretations", status_code=201)
def add_interpretation(
    test_id: uuid.UUID,
    payload: InterpretationCreate,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> dict:
    t = db.get(PsychTest, test_id)
    if t is None:
        raise HTTPException(status_code=404, detail="ابزار یافت نشد")
    if payload.score_max < payload.score_min:
        raise HTTPException(status_code=422, detail="حد بالای بازه نمی‌تواند کمتر از حد پایین باشد")
    i = PsychInterpretation(
        test_id=test_id,
        score_min=payload.score_min,
        score_max=payload.score_max,
        label=payload.label.strip(),
        guidance=payload.guidance,
        sort_order=payload.sort_order,
    )
    db.add(i)
    if t.status == PsychStatus.PUBLISHED:
        t.status = PsychStatus.DRAFT
        t.review_note = None
        t.reviewed_by = None
        t.reviewed_at = None
    db.commit()
    db.refresh(i)
    return _interp_out(i)


@router.delete("/psych-tests/{test_id}/interpretations/{interp_id}", status_code=204)
def delete_interpretation(
    test_id: uuid.UUID,
    interp_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*MANAGE_ROLES)),
) -> None:
    i = db.get(PsychInterpretation, interp_id)
    if i is None or i.test_id != test_id:
        raise HTTPException(status_code=404, detail="بازه تفسیر یافت نشد")
    db.delete(i)
    t = db.get(PsychTest, test_id)
    if t and t.status == PsychStatus.PUBLISHED:
        t.status = PsychStatus.DRAFT
        t.review_note = None
        t.reviewed_by = None
        t.reviewed_at = None
    db.commit()


@router.get("/psych-tests/{test_id}/interpretations")
def list_interpretations(
    test_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*VIEW_ROLES)),
) -> dict:
    rows = db.scalars(
        select(PsychInterpretation)
        .where(PsychInterpretation.test_id == test_id)
        .order_by(PsychInterpretation.sort_order, PsychInterpretation.score_min)
    ).all()
    return {"items": [_interp_out(i) for i in rows]}


@router.get("/psych-tests/{test_id}/attempts")
def list_attempts(
    test_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*VIEW_ROLES)),
) -> dict:
    rows = db.scalars(
        select(PsychAttempt)
        .where(PsychAttempt.test_id == test_id)
        .order_by(PsychAttempt.created_at.desc())
        .limit(200)
    ).all()
    return {"items": [_attempt_out(a) for a in rows]}


# ---------------------------------------------------------------- عمومی و اجرا
@router.get("/public/psych-tests")
def public_tests(db: Session = Depends(get_db)) -> dict:
    """فقط ابزارهای منتشرشده (تأیید ناظر علمی — D08)."""
    rows = db.scalars(
        select(PsychTest)
        .where(PsychTest.status == PsychStatus.PUBLISHED)
        .order_by(PsychTest.sort_order, PsychTest.created_at.desc())
    ).all()
    out = []
    for t in rows:
        topic = db.get(Topic, t.topic_id) if t.topic_id else None
        if topic is not None and not topic.is_active:
            continue
        qc = db.scalar(select(func.count()).select_from(PsychQuestion).where(PsychQuestion.test_id == t.id)) or 0
        out.append(
            {
                "id": str(t.id),
                "slug": t.slug,
                "title": t.title,
                "description": t.description,
                "topic_name": topic.name if topic else None,
                # فاز ۵۰ - متادیتای کاتالوگ مرجع
                "code": t.code,
                "age_range": t.age_range,
                "estimated_minutes": t.estimated_minutes,
                "accent_color": t.accent_color,
                "sort_order": t.sort_order,
                "question_count": int(qc),
            }
        )
    return {"items": out}


@router.get("/public/psych-images/{file_path:path}")
def public_psych_image(file_path: str) -> FileResponse:
    """فاز ۵۰ - سرو عکس پیوست سؤال از uploads/psych_images (فقط-خواندنی، ضد Traversal)."""
    base = Path("uploads/psych_images").resolve()
    target = (base / file_path).resolve()
    if base not in target.parents and target != base:
        raise HTTPException(status_code=404, detail="تصویر یافت نشد")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="تصویر یافت نشد")
    mime = "image/png" if target.suffix.lower() == ".png" else "image/jpeg"
    return FileResponse(target, media_type=mime)


@router.get("/public/psych-tests/{slug}/paper")
def public_paper(slug: str, db: Session = Depends(get_db)) -> dict:
    """پرسش‌نامه ابزار منتشرشده — امتیاز گزینه‌ها هرگز به کلاینت نمی‌رود."""
    t = db.scalars(
        select(PsychTest).where(PsychTest.slug == slug, PsychTest.status == PsychStatus.PUBLISHED)
    ).first()
    if t is None:
        raise HTTPException(status_code=404, detail="ابزار منتشرنشده است")
    questions = db.scalars(
        select(PsychQuestion).where(PsychQuestion.test_id == t.id).order_by(PsychQuestion.sort_order)
    ).all()
    return {
        "test": {
            "id": str(t.id),
            "slug": t.slug,
            "title": t.title,
            "description": t.description,
            "code": t.code,
            "age_range": t.age_range,
            "estimated_minutes": t.estimated_minutes,
            "accent_color": t.accent_color,
        },
        "questions": [
            {
                "id": str(q.id),
                "prompt": q.prompt,
                "subscale": q.subscale,
                "options": [o.get("label") for o in (q.options or [])],
                "image_url": f"/api/v1/public/psych-images/{q.image_path}" if q.image_path else None,
                "sort_order": q.sort_order,
            }
            for q in questions
        ],
    }


@router.post("/public/psych-tests/{slug}/attempts", status_code=201)
def take_test(
    slug: str,
    payload: AttemptCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    """اجرای تست — نمره‌دهی و تفسیر سمت سرور؛ snapshot نتیجه."""
    t = db.scalars(
        select(PsychTest).where(PsychTest.slug == slug, PsychTest.status == PsychStatus.PUBLISHED)
    ).first()
    if t is None:
        raise HTTPException(status_code=404, detail="ابزار منتشرنشده است")
    questions = db.scalars(
        select(PsychQuestion).where(PsychQuestion.test_id == t.id).order_by(PsychQuestion.sort_order)
    ).all()
    if not questions:
        raise HTTPException(status_code=422, detail="ابزار بدون سؤال قابل برگزاری نیست")
    answers = payload.answers
    for a in answers:
        if not isinstance(a, int) or a < 0:
            raise HTTPException(status_code=422, detail="پاسخ‌ها باید اندیس گزینه باشند")
    for idx, q in enumerate(questions):
        if idx < len(answers) and answers[idx] >= len(q.options or []):
            raise HTTPException(status_code=422, detail="اندیس پاسخ خارج از محدوده گزینه‌هاست")
    score = 0
    for idx, q in enumerate(questions):
        if idx < len(answers):
            opts = q.options or []
            try:
                score += int(opts[answers[idx]].get("score", 0))
            except (IndexError, TypeError, ValueError):
                pass
    # فاز ۴۷ - ریزنمره زیرمقیاس‌ها (اختیاری): سؤال‌های با subscale جمع جداگانه می‌شوند
    subscale_scores: dict[str, int] = {}
    for idx, q in enumerate(questions):
        if q.subscale and idx < len(answers):
            opts = q.options or []
            try:
                subscale_scores[q.subscale] = subscale_scores.get(q.subscale, 0) + int(
                    opts[answers[idx]].get("score", 0)
                )
            except (IndexError, TypeError, ValueError):
                pass
    interp = db.scalars(
        select(PsychInterpretation)
        .where(
            PsychInterpretation.test_id == t.id,
            PsychInterpretation.score_min <= score,
            PsychInterpretation.score_max >= score,
        )
        .order_by(PsychInterpretation.sort_order, PsychInterpretation.score_min)
    ).first()
    if interp is None:
        raise HTTPException(
            status_code=422, detail="بازه تفسیر برای این نمره تعریف نشده است؛ با پشتیبانی تماس بگیرید"
        )
    a = PsychAttempt(
        test_id=t.id,
        user_id=actor.id,
        score=score,
        interpretation_label=interp.label,
        interpretation_guidance=interp.guidance,
        answers=answers,
        subscale_scores=subscale_scores or None,
        demographics=payload.demographics or None,
    )
    # فاز ۶۳ - گزارش تحلیلی چندلایه (مقیاس‌ها/سطح‌ها) — snapshot
    a.result_payload = build_report_payload(
        db, t, questions, answers, total_score=score,
        total_max=sum(max(int(o.get("score", 0)) for o in (q.options or [{}])) for q in questions),
        total_label=interp.label, total_guidance=interp.guidance,
    )
    db.add(a)
    # فاز ۷۰ - پروندهٔ مشاورهٔ کاربر خودکار ساخته/به‌روز می‌شود (تاریخچه با زمان)
    from app.services import counseling_file as cf

    cf.ensure_file(db, actor)
    cf.touch_file(db, actor.id)
    db.commit()
    db.refresh(a)
    return {
        "attempt": _attempt_out(a),
        "disclaimer": "این نتیجه ابزار غربالگری است و جایگزین ارزیابی بالینی مشاور نیست",
    }


@router.get("/my/psych-results")
def my_results(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    rows = db.scalars(
        select(PsychAttempt)
        .where(PsychAttempt.user_id == actor.id)
        .order_by(PsychAttempt.created_at.desc())
        .limit(100)
    ).all()
    out = []
    for a in rows:
        t = db.get(PsychTest, a.test_id)
        item = _attempt_out(a)
        item["test_title"] = t.title if t else None
        out.append(item)
    return {"items": out}


# ---------------------------------------------------------------- فاز ۷۰
# لیست آزمون‌های برگزارشده (پرسنل) + پرونده‌سازی از روی آزمون + نتایج دیده‌شده
@router.post("/my/psych-results/{attempt_id}/viewed")
def mark_result_viewed(
    attempt_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    """ثبت «دیده‌شدن» نتیجهٔ آزمون توسط خود کاربر — زمان اولین بازدید ثبت می‌ماند."""
    a = db.get(PsychAttempt, attempt_id)
    if a is None or a.user_id != actor.id:
        raise HTTPException(status_code=404, detail="نتیجهٔ آزمون یافت نشد")
    if a.viewed_at is None:
        from datetime import datetime as _dt, timezone as _tz

        a.viewed_at = _dt.now(_tz.utc)
        from app.services import counseling_file as cf

        cf.touch_file(db, actor.id)
        db.commit()
    return {"status": "ok", "viewed_at": a.viewed_at.isoformat()}


@router.get("/psych-attempts")
def list_all_attempts(
    test_id: uuid.UUID | None = Query(default=None),
    q: str = Query(default="", max_length=100),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> dict:
    """آزمون‌های برگزارشده — «چه کسی، کدام آزمون، چه زمانی، چه نمره‌ای».

    فاز ۷۱ — جداسازی داده:
    - کارکنان (پذیرش/مدیر/مشاور/مسئول فنی): کل آزمون‌های سامانه با هویت
      آزمون‌دهنده، نمره، تفسیر، وضعیت دیده‌شدن و پروندهٔ متصل؛
    - سایر کاربران (مثلاً متقاضی): «فقط آزمون‌های خودش» — نه بیشتر.
    """
    from app.models.rbac import effective_permissions

    actor_roles = {r.code for r in actor.roles}
    is_staff = bool(actor_roles.intersection(set(VIEW_ROLES))) or "*" in effective_permissions(actor.roles)
    stmt = (
        select(PsychAttempt, PsychTest, User)
        .join(PsychTest, PsychAttempt.test_id == PsychTest.id)
        .join(User, PsychAttempt.user_id == User.id)
    )
    if not is_staff:
        stmt = stmt.where(PsychAttempt.user_id == actor.id)
    if test_id is not None:
        stmt = stmt.where(PsychAttempt.test_id == test_id)
    if (term := (q or "").strip()):
        like = f"%{term}%"
        stmt = stmt.where(or_(
            User.display_name.ilike(like),
            User.username.ilike(like),
            User.mobile.ilike(like),
            PsychTest.title.ilike(like),
        ))
    rows = db.execute(
        stmt.order_by(PsychAttempt.created_at.desc()).limit(limit)
    ).all()
    case_ids = [a.case_id for a, _t, _u in rows if a.case_id]
    case_numbers: dict[uuid.UUID, str] = {}
    if case_ids:
        from app.models.case import Case

        case_numbers = {
            c.id: c.case_number
            for c in db.scalars(select(Case).where(Case.id.in_(case_ids))).all()
        }
    items = []
    for a, t, u in rows:
        item = _attempt_out(a)
        item.update({
            "test_title": t.title,
            "test_slug": t.slug,
            "user_display_name": u.display_name,
            "user_username": u.username,
            "user_mobile": u.mobile,
            "case_number": case_numbers.get(a.case_id) if a.case_id else None,
        })
        items.append(item)
    return {"items": items, "total": len(items)}


class CreateCaseFromAttempt(BaseModel):
    """پارامترهای اختیاری ایجاد پرونده از روی آزمون."""
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    service_location_id: uuid.UUID | None = None


@router.post("/psych-attempts/{attempt_id}/create-case", status_code=201)
def create_case_from_attempt(
    attempt_id: uuid.UUID,
    payload: CreateCaseFromAttempt | None = None,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION")),
) -> dict:
    """ایجاد پرونده برای «کسی که آزمون داده» — هویت او مشخص و پرونده‌سازی می‌شود.

    - متقاضی از حساب آزمون‌دهنده پیدا/ساخته می‌شود (اتصال user_id، وگرنه
      موبایل، وگرنه ساخت از نام نمایشی)؛
    - اگر همین کاربر قبلاً پرونده‌ای از آزمون داشته باشد، همان پرونده استفاده
      می‌شود (idempotent) و آزمون‌های بی‌پروندهٔ او هم به آن متصل می‌شوند؛
    - پروندهٔ جدید با وضعیت awaiting_assignment ثبت می‌شود تا پذیرش مشاور
      تعیین کند.
    """
    from app.models.case import Case, CaseStatus
    from app.models.people import Applicant
    from app.api.v1.cases import generate_case_number
    from app.services.audit import record_audit

    a = db.get(PsychAttempt, attempt_id)
    if a is None:
        raise HTTPException(status_code=404, detail="آزمون یافت نشد")
    owner = db.get(User, a.user_id)
    if owner is None:
        raise HTTPException(status_code=422, detail="حساب آزمون‌دهنده یافت نشد")
    payload = payload or CreateCaseFromAttempt()

    # --- متقاضی: اتصال مستقیم، وگرنه موبایل، وگرنه ساخت جدید
    applicant = db.scalar(select(Applicant).where(Applicant.user_id == owner.id))
    applicant_created = False
    if applicant is None:
        mobile = (owner.mobile or "").strip()
        if mobile and mobile != owner.username:
            applicant = db.scalar(select(Applicant).where(Applicant.mobile == mobile))
        if applicant is None and mobile:
            applicant = db.scalar(select(Applicant).where(Applicant.mobile == mobile))
        if applicant is None:
            disp = (payload.first_name or "").strip() or owner.display_name.strip()
            parts = disp.split(" ", 1)
            first = parts[0] if parts else disp
            last = (payload.last_name or "").strip() or (parts[1] if len(parts) > 1 else "—")
            applicant = Applicant(
                first_name=first[:100], last_name=last[:100],
                mobile=mobile or None,
                status="active", record_source="manual",
                user_id=owner.id,
            )
            db.add(applicant)
            db.flush()
            applicant_created = True

    # --- پروندهٔ موجود همین کاربر یا ساخت پروندهٔ جدید
    linked_existing = False
    case = db.execute(
        select(Case)
        .join(PsychAttempt, PsychAttempt.case_id == Case.id)
        .where(PsychAttempt.user_id == owner.id)
        .order_by(Case.created_at.desc())
        .limit(1)
    ).scalars().first()
    if case is None:
        case = Case(
            case_number=generate_case_number(db),
            applicant_id=applicant.id,
            acceptance_date=datetime.now(timezone.utc).date(),
            service_location_id=payload.service_location_id,
            service_type="ارزیابی و آزمون‌های روان‌شناسی",
            status=CaseStatus.AWAITING_ASSIGNMENT,
            created_by=actor.id,
        )
        db.add(case)
        db.flush()
    else:
        linked_existing = True

    # --- اتصال همهٔ آزمون‌های بی‌پروندهٔ همین کاربر
    unlinked = db.scalars(
        select(PsychAttempt).where(
            PsychAttempt.user_id == owner.id, PsychAttempt.case_id.is_(None)
        )
    ).all()
    for ua in unlinked:
        ua.case_id = case.id

    from app.services import counseling_file as cf

    cf.ensure_file(db, owner)
    cf.touch_file(db, owner.id)
    db.commit()
    record_audit(db, action="psych_attempt.case_created", actor_user_id=actor.id,
                 entity_type="case", entity_id=str(case.id),
                 detail={"attempt_id": str(a.id), "user_id": str(owner.id),
                         "linked_attempts": len(unlinked)})
    return {
        "case_id": str(case.id),
        "case_number": case.case_number,
        "case_created": not linked_existing,
        "applicant_id": str(applicant.id),
        "applicant_created": applicant_created,
        "linked_attempts": len(unlinked),
    }


@router.get("/cases/{case_id}/psych-attempts")
def case_psych_attempts(
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: User = Depends(require_roles(*VIEW_ROLES)),
) -> dict:
    """نتایج آزمون‌های متصل به پرونده — تب «نتایج آزمون» صفحهٔ پرونده."""
    from app.models.case import Case

    if db.get(Case, case_id) is None:
        raise HTTPException(status_code=404, detail="پرونده یافت نشد")
    rows = db.execute(
        select(PsychAttempt, PsychTest, User)
        .join(PsychTest, PsychAttempt.test_id == PsychTest.id)
        .join(User, PsychAttempt.user_id == User.id)
        .where(PsychAttempt.case_id == case_id)
        .order_by(PsychAttempt.created_at.desc())
        .limit(200)
    ).all()
    items = []
    for a, t, u in rows:
        item = _attempt_out(a)
        item.update({
            "test_title": t.title,
            "test_slug": t.slug,
            "user_display_name": u.display_name,
        })
        items.append(item)
    return {"items": items}
