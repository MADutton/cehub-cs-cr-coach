from __future__ import annotations
import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .database import AsyncSessionLocal, Enrollment, Event, Review, Submission, User, engine, get_db, init_db
from .extractor import extract_text
from .scorer import run_ai_review

logger = logging.getLogger("cehub.coach")


def _hash_email(email: Optional[str]) -> Optional[str]:
    if not email:
        return None
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


async def _alter_safe(sql: str):
    try:
        async with engine.begin() as conn:
            await conn.execute(text(sql))
    except Exception:
        pass


async def _run_migrations():
    """Backfill schema for additive Phase 1 columns; idempotent."""
    await _alter_safe("ALTER TABLE users ADD COLUMN user_hash VARCHAR(64)")
    await _alter_safe("ALTER TABLE submissions ADD COLUMN submission_uuid VARCHAR(36)")
    await _alter_safe("ALTER TABLE submissions ADD COLUMN rmv_type VARCHAR(32) DEFAULT 'case_review'")
    await _alter_safe("ALTER TABLE submissions ADD COLUMN attempt_number INTEGER DEFAULT 1")
    await _alter_safe("ALTER TABLE reviews ADD COLUMN previous_pct DOUBLE PRECISION")
    await _alter_safe("ALTER TABLE reviews ADD COLUMN score_delta DOUBLE PRECISION")
    await _alter_safe("ALTER TABLE reviews ADD COLUMN model_version VARCHAR(100)")

    # Backfill: user_hash for users with email but no hash
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.user_hash == None, User.email.isnot(None)))
        for u in result.scalars().all():
            u.user_hash = _hash_email(u.email)
        await db.commit()

    # Backfill: submission_uuid for legacy rows
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Submission).where(Submission.submission_uuid == None))
        for s in result.scalars().all():
            s.submission_uuid = str(uuid.uuid4())
        await db.commit()


async def _log_event(
    db: AsyncSession,
    event_type: str,
    *,
    user_id: Optional[int] = None,
    submission_id: Optional[int] = None,
    submission_uuid: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
):
    db.add(Event(
        event_uuid=str(uuid.uuid4()),
        event_type=event_type,
        user_id=user_id,
        submission_id=submission_id,
        submission_uuid=submission_uuid,
        payload=payload,
        created_at=int(time.time() * 1000),
    ))


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await _run_migrations()
    yield


app = FastAPI(title="CEHub CS/CR Coach", lifespan=lifespan)

_default_origins = [
    "https://cehub.vet",
    "https://www.cehub.vet",
    "https://cehub-vet.thinkific.com",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
_env_origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_default_origins + _env_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

_STATIC = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_STATIC):
    app.mount("/static", StaticFiles(directory=_STATIC), name="static")

    @app.get("/", include_in_schema=False)
    async def _index():
        return FileResponse(os.path.join(_STATIC, "index.html"))


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Thinkific webhook ─────────────────────────────────────────────────────────

@app.post("/webhooks/thinkific")
async def thinkific_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    # Thinkific basic webhooks (Grow plan) do not send an HMAC header.
    # We authenticate via a shared secret passed as a URL query param.
    # Webhook URL in Thinkific must be: .../webhooks/thinkific?secret=YOUR_SECRET
    secret = os.environ.get("THINKIFIC_WEBHOOK_SECRET")
    if not secret:
        logger.error("THINKIFIC_WEBHOOK_SECRET is not set; refusing webhook")
        raise HTTPException(503, "Webhook receiver is not configured.")

    provided = request.query_params.get("secret", "")
    if not hmac.compare_digest(provided, secret):
        logger.warning("Thinkific webhook secret mismatch")
        raise HTTPException(401, "Invalid secret.")

    raw = await request.body()
    try:
        body = json.loads(raw.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid JSON.")

    resource = body.get("resource")
    action = body.get("action")
    if resource != "enrollment":
        return {"ok": True, "skipped": f"resource={resource}"}

    payload = body.get("payload") or {}
    enrollment_id = str(payload.get("id") or "")
    course_id = str(payload.get("course_id") or "")
    user_obj = payload.get("user") or {}
    thinkific_user_id = str(user_obj.get("id") or "")
    user_email = user_obj.get("email")
    first = (user_obj.get("first_name") or "").strip()
    last = (user_obj.get("last_name") or "").strip()
    user_name = (first + " " + last).strip() or None
    expiry_date = payload.get("expiry_date")

    if not enrollment_id or not thinkific_user_id:
        raise HTTPException(400, "Webhook payload missing enrollment id or user id.")

    target_course = os.environ.get("THINKIFIC_COURSE_ID", "").strip()
    if target_course and course_id != target_course:
        return {"ok": True, "skipped": f"course_id={course_id} not target {target_course}"}
    if not target_course:
        logger.warning(
            "THINKIFIC_COURSE_ID is not set; accepting enrollment for course_id=%s.",
            course_id,
        )

    now_ms = int(time.time() * 1000)
    existing_r = await db.execute(
        select(Enrollment).where(Enrollment.thinkific_enrollment_id == enrollment_id)
    )
    existing = existing_r.scalar_one_or_none()

    if action in ("created", "updated"):
        if existing:
            existing.thinkific_user_id = thinkific_user_id
            existing.course_id = course_id or existing.course_id
            existing.user_email = user_email or existing.user_email
            existing.user_name = user_name or existing.user_name
            existing.expiry_date = expiry_date
            existing.revoked = False
            existing.updated_at = now_ms
        else:
            db.add(Enrollment(
                thinkific_enrollment_id=enrollment_id,
                thinkific_user_id=thinkific_user_id,
                course_id=course_id or None,
                user_email=user_email,
                user_name=user_name,
                expiry_date=expiry_date,
                revoked=False,
                created_at=now_ms,
                updated_at=now_ms,
            ))
        await db.commit()
        return {"ok": True, "action": action, "enrollment_id": enrollment_id}

    if action == "deleted":
        if existing:
            existing.revoked = True
            existing.updated_at = now_ms
            await db.commit()
        return {"ok": True, "action": "deleted", "enrollment_id": enrollment_id}

    return {"ok": True, "skipped": f"action={action}"}


# ── Admin: manual enrollment seed ────────────────────────────────────────────

@app.post("/admin/seed-enrollment")
async def seed_enrollment(
    email: str = Form(...),
    thinkific_user_id: str = Form(...),
    admin_secret: str = Form(...),
    enrollment_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    expected = os.environ.get("ADMIN_SECRET", "")
    if not expected or not hmac.compare_digest(admin_secret, expected):
        raise HTTPException(403, "Invalid admin secret.")

    import secrets as _secrets
    eid = (enrollment_id or "").strip() or f"admin-{_secrets.token_hex(8)}"

    now_ms = int(time.time() * 1000)
    existing_r = await db.execute(
        select(Enrollment).where(Enrollment.thinkific_enrollment_id == eid)
    )
    existing = existing_r.scalar_one_or_none()
    if existing:
        existing.user_email = email.strip().lower()
        existing.thinkific_user_id = thinkific_user_id
        existing.revoked = False
        existing.updated_at = now_ms
    else:
        db.add(Enrollment(
            thinkific_enrollment_id=eid,
            thinkific_user_id=thinkific_user_id,
            course_id=os.environ.get("THINKIFIC_COURSE_ID"),
            user_email=email.strip().lower(),
            revoked=False,
            created_at=now_ms,
            updated_at=now_ms,
        ))
    await db.commit()
    logger.warning("Admin seeded enrollment: email=%s enrollment_id=%s", email, eid)
    return {"ok": True, "enrollment_id": eid, "email": email}


# ── User ──────────────────────────────────────────────────────────────────────

@app.post("/api/identify-by-email")
async def identify_by_email(
    email: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    enr_r = await db.execute(
        select(Enrollment).where(
            Enrollment.user_email == email.strip().lower(),
            Enrollment.revoked == False,
        )
    )
    enr = enr_r.scalar_one_or_none()
    if not enr:
        raise HTTPException(
            403,
            "No active enrollment found for that email. Make sure it matches "
            "the email you used to purchase at cehub.vet. "
            "Contact support@cehub.vet if the problem persists."
        )

    now = int(time.time() * 1000)
    user_r = await db.execute(
        select(User).where(User.thinkific_user_id == enr.thinkific_user_id)
    )
    user = user_r.scalar_one_or_none()
    if not user:
        user = User(
            thinkific_user_id=enr.thinkific_user_id,
            email=enr.user_email,
            name=enr.user_name,
            enrollment_id=enr.thinkific_enrollment_id,
            user_hash=_hash_email(enr.user_email) if enr.user_email else None,
            created_at=now,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    elif enr.user_email and not user.user_hash:
        user.user_hash = _hash_email(enr.user_email)
        await db.commit()

    return {
        "user_id": user.id,
        "thinkific_user_id": user.thinkific_user_id,
        "email": enr.user_email,
        "name": enr.user_name,
        "enrollment_id": enr.thinkific_enrollment_id,
    }

@app.post("/api/identify")
async def identify(
    thinkific_user_id: str = Form(...),
    email: Optional[str] = Form(None),
    name: Optional[str] = Form(None),
    enrollment_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.thinkific_user_id == thinkific_user_id))
    user = result.scalar_one_or_none()
    now = int(time.time() * 1000)
    if not user:
        user = User(
            thinkific_user_id=thinkific_user_id,
            email=email, name=name,
            enrollment_id=enrollment_id,
            user_hash=_hash_email(email) if email else None,
            created_at=now,
        )
        db.add(user)
    else:
        if email:
            user.email = email
            user.user_hash = _hash_email(email)
        if name:
            user.name = name
        if enrollment_id:
            user.enrollment_id = enrollment_id
    await db.commit()
    await db.refresh(user)
    return {"user_id": user.id, "thinkific_user_id": user.thinkific_user_id,
            "email": user.email, "name": user.name}


# ── Submissions ───────────────────────────────────────────────────────────────

@app.get("/api/submissions")
async def list_submissions(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Submission)
        .where(Submission.user_id == user_id)
        .order_by(Submission.created_at.desc())
    )
    subs = result.scalars().all()
    out = []
    for s in subs:
        rev_r = await db.execute(select(Review).where(Review.submission_id == s.id))
        rev = rev_r.scalar_one_or_none()
        out.append({
            "id": s.id,
            "submission_uuid": s.submission_uuid,
            "rmv_type": s.rmv_type,
            "submission_type": s.submission_type,
            "filename": s.filename,
            "word_count": s.word_count,
            "version_number": s.version_number,
            "attempt_number": s.attempt_number,
            "review_status": s.review_status,
            "created_at": s.created_at,
            "estimated_total": rev.estimated_total if rev else None,
            "estimated_max": rev.estimated_max if rev else None,
            "estimated_pct": rev.estimated_pct if rev else None,
            "previous_pct": rev.previous_pct if rev else None,
            "score_delta": rev.score_delta if rev else None,
            "estimated_pass": rev.estimated_pass if rev else None,
        })
    return {"submissions": out}


@app.post("/api/submissions")
async def create_submission(
    background_tasks: BackgroundTasks,
    user_id: int = Form(...),
    submission_type: str = Form(...),
    file: UploadFile = File(...),
    enrollment_id: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    if submission_type not in ("case_summary", "case_report"):
        raise HTTPException(400, "submission_type must be case_summary or case_report")

    user_r = await db.execute(select(User).where(User.id == user_id))
    user = user_r.scalar_one_or_none()
    if not user:
        raise HTTPException(403, "Unknown user. Please re-open this tool from your CEHub course.")

    # Allowlist gate: enrollment must have been registered via Thinkific webhook,
    # must belong to this Thinkific user, and must not be revoked.
    enr_r = await db.execute(
        select(Enrollment).where(Enrollment.thinkific_enrollment_id == enrollment_id)
    )
    enr = enr_r.scalar_one_or_none()
    if not enr:
        raise HTTPException(
            403,
            "Your enrollment is not yet active. If you just purchased, please refresh "
            "this page in a moment. If the problem persists, contact support@cehub.vet."
        )
    if enr.thinkific_user_id != user.thinkific_user_id:
        raise HTTPException(403, "This enrollment does not belong to your account.")
    if enr.revoked:
        raise HTTPException(403, "This enrollment has been revoked.")

    # One submission per purchase.
    gate_r = await db.execute(
        select(Submission).where(Submission.enrollment_id == enrollment_id)
    )
    if gate_r.scalar_one_or_none():
        raise HTTPException(
            403,
            "Your submission for this purchase has already been used. "
            "Purchase a new session at cehub.vet to submit another draft."
        )

    content = await file.read()
    extracted, word_count, err = await extract_text(content, file.filename or "")
    if err and not extracted:
        raise HTTPException(400, f"Could not extract text: {err}")

    # Attempt count across all prior submissions of the same type for this user
    # (Q2 option ii): a new purchase + new submission counts as the next attempt.
    attempt_r = await db.execute(
        select(func.count()).select_from(Submission)
        .where(
            Submission.user_id == user_id,
            Submission.submission_type == submission_type,
        )
    )
    attempt_number = (attempt_r.scalar() or 0) + 1

    now = int(time.time() * 1000)
    sub_uuid = str(uuid.uuid4())
    sub = Submission(
        submission_uuid=sub_uuid,
        rmv_type="case_review",
        user_id=user_id,
        enrollment_id=enrollment_id,
        submission_type=submission_type,
        filename=file.filename,
        extracted_text=extracted,
        word_count=word_count,
        version_number=1,
        attempt_number=attempt_number,
        review_status="running",
        created_at=now,
    )
    db.add(sub)
    await db.commit()
    await db.refresh(sub)

    await _log_event(
        db, "case_upload",
        user_id=user_id,
        submission_id=sub.id,
        submission_uuid=sub_uuid,
        payload={
            "submission_type": submission_type,
            "filename": file.filename,
            "word_count": word_count,
            "attempt_number": attempt_number,
            "enrollment_id": enrollment_id,
        },
    )
    await db.commit()

    background_tasks.add_task(_review_task, sub.id)
    return {
        "submission_id": sub.id,
        "submission_uuid": sub_uuid,
        "version_number": 1,
        "attempt_number": attempt_number,
        "word_count": word_count,
    }


@app.get("/api/submissions/{submission_id}")
async def get_submission(submission_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Submission).where(Submission.id == submission_id))
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(404, "Not found")

    rev_r = await db.execute(select(Review).where(Review.submission_id == submission_id))
    rev = rev_r.scalar_one_or_none()

    return {
        "id": sub.id,
        "submission_uuid": sub.submission_uuid,
        "rmv_type": sub.rmv_type,
        "user_id": sub.user_id,
        "submission_type": sub.submission_type,
        "filename": sub.filename, "word_count": sub.word_count,
        "version_number": sub.version_number,
        "attempt_number": sub.attempt_number,
        "review_status": sub.review_status,
        "created_at": sub.created_at,
        "review": {
            "section_scores": rev.section_scores,
            "overall_impression_a": rev.overall_impression_a,
            "overall_impression_a_rationale": rev.overall_impression_a_rationale,
            "overall_impression_b": rev.overall_impression_b,
            "overall_impression_b_rationale": rev.overall_impression_b_rationale,
            "word_count_estimate": rev.word_count_estimate,
            "word_count_pass": rev.word_count_pass,
            "word_count_note": rev.word_count_note,
            "formatting_deductions": rev.formatting_deductions,
            "formatting_notes": rev.formatting_notes,
            "estimated_total": rev.estimated_total,
            "estimated_max": rev.estimated_max,
            "estimated_pass_score": rev.estimated_pass_score,
            "estimated_pct": rev.estimated_pct,
            "previous_pct": rev.previous_pct,
            "score_delta": rev.score_delta,
            "estimated_pass": rev.estimated_pass,
            "auto_fail_reasons": rev.auto_fail_reasons,
            "flags": rev.flags,
            "strengths": rev.strengths,
            "weaknesses": rev.weaknesses,
            "model_version": rev.model_version,
            "reviewed_at": rev.reviewed_at,
        } if rev else None,
    }


@app.get("/api/progress")
async def get_progress(user_id: int, submission_type: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Submission)
        .where(Submission.user_id == user_id, Submission.submission_type == submission_type)
        .order_by(Submission.created_at.asc())
    )
    history = []
    for s in result.scalars().all():
        rev_r = await db.execute(select(Review).where(Review.submission_id == s.id))
        rev = rev_r.scalar_one_or_none()
        if rev and s.review_status == "done":
            history.append({
                "submission_id": s.id,
                "submission_uuid": s.submission_uuid,
                "version_number": s.version_number,
                "attempt_number": s.attempt_number,
                "created_at": s.created_at,
                "estimated_total": rev.estimated_total,
                "estimated_max": rev.estimated_max,
                "estimated_pct": rev.estimated_pct,
                "previous_pct": rev.previous_pct,
                "score_delta": rev.score_delta,
                "estimated_pass": rev.estimated_pass,
                "section_scores": {k: v.get("score", 0) for k, v in (rev.section_scores or {}).items()},
            })
    return {"history": history}


# ── Background task ───────────────────────────────────────────────────────────

async def _review_task(submission_id: int):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Submission).where(Submission.id == submission_id))
        sub = result.scalar_one_or_none()
        if not sub:
            return
        try:
            data = await run_ai_review(sub.submission_type, sub.extracted_text or "")
            now = int(time.time() * 1000)

            # Score delta vs. most recent prior completed review of the same type for this user
            prior_r = await db.execute(
                select(Review.estimated_pct)
                .join(Submission, Review.submission_id == Submission.id)
                .where(
                    Submission.user_id == sub.user_id,
                    Submission.submission_type == sub.submission_type,
                    Submission.id != sub.id,
                    Submission.review_status == "done",
                    Review.estimated_pct.isnot(None),
                )
                .order_by(Review.reviewed_at.desc())
                .limit(1)
            )
            prior_pct = prior_r.scalar()
            current_pct = data.get("estimated_pct")
            score_delta = (
                (current_pct - prior_pct)
                if (prior_pct is not None and current_pct is not None)
                else None
            )

            rev = Review(
                submission_id=submission_id,
                section_scores=data.get("section_scores"),
                overall_impression_a=data.get("overall_impression_a", {}).get("pass"),
                overall_impression_a_rationale=data.get("overall_impression_a", {}).get("rationale"),
                overall_impression_b=data.get("overall_impression_b", {}).get("pass"),
                overall_impression_b_rationale=data.get("overall_impression_b", {}).get("rationale"),
                word_count_estimate=data.get("word_count_estimate"),
                word_count_pass=data.get("word_count_pass"),
                word_count_note=data.get("word_count_note"),
                formatting_deductions=data.get("formatting_deductions", 0),
                formatting_notes=data.get("formatting_notes", []),
                estimated_total=data.get("estimated_total"),
                estimated_max=data.get("estimated_max"),
                estimated_pass_score=data.get("estimated_pass_score"),
                estimated_pct=current_pct,
                previous_pct=prior_pct,
                score_delta=score_delta,
                estimated_pass=data.get("estimated_pass"),
                auto_fail_reasons=data.get("auto_fail_reasons", []),
                flags=data.get("flags", []),
                strengths=data.get("strengths", []),
                weaknesses=data.get("weaknesses", []),
                model_version=os.environ.get("OPENAI_MODEL", "gpt-4o"),
                reviewed_at=now,
            )
            db.add(rev)
            sub.review_status = "done"
            await _log_event(
                db, "case_review_scored",
                user_id=sub.user_id,
                submission_id=sub.id,
                submission_uuid=sub.submission_uuid,
                payload={
                    "submission_type": sub.submission_type,
                    "attempt_number": sub.attempt_number,
                    "estimated_pct": current_pct,
                    "previous_pct": prior_pct,
                    "score_delta": score_delta,
                    "estimated_pass": data.get("estimated_pass"),
                    "model_version": os.environ.get("OPENAI_MODEL", "gpt-4o"),
                },
            )
            await db.commit()
        except Exception as e:
            sub.review_status = "error"
            await _log_event(
                db, "case_review_error",
                user_id=sub.user_id,
                submission_id=sub.id,
                submission_uuid=sub.submission_uuid,
                payload={"error": str(e)[:500]},
            )
            await db.commit()
            raise


