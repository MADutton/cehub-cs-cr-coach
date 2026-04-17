from __future__ import annotations
import os
import time
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import AsyncSessionLocal, Review, Submission, User, get_db, init_db
from .extractor import extract_text
from .scorer import run_ai_review


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="CEHub CS/CR Coach", lifespan=lifespan)

_default_origins = [
    "https://cehub.vet",
    "https://www.cehub.vet",
    "https://cehub.thinkific.com",
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


# ── User ──────────────────────────────────────────────────────────────────────

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
            created_at=now,
        )
        db.add(user)
    else:
        if email:
            user.email = email
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
            "submission_type": s.submission_type,
            "filename": s.filename,
            "word_count": s.word_count,
            "version_number": s.version_number,
            "review_status": s.review_status,
            "created_at": s.created_at,
            "estimated_total": rev.estimated_total if rev else None,
            "estimated_max": rev.estimated_max if rev else None,
            "estimated_pct": rev.estimated_pct if rev else None,
            "estimated_pass": rev.estimated_pass if rev else None,
        })
    return {"submissions": out}


@app.post("/api/submissions")
async def create_submission(
    background_tasks: BackgroundTasks,
    user_id: int = Form(...),
    submission_type: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    if submission_type not in ("case_summary", "case_report"):
        raise HTTPException(400, "submission_type must be case_summary or case_report")

    content = await file.read()
    text, word_count, err = await extract_text(content, file.filename or "")
    if err and not text:
        raise HTTPException(400, f"Could not extract text: {err}")

    existing_r = await db.execute(
        select(Submission).where(
            Submission.user_id == user_id,
            Submission.submission_type == submission_type,
        )
    )
    version = len(existing_r.scalars().all()) + 1

    now = int(time.time() * 1000)
    sub = Submission(
        user_id=user_id,
        submission_type=submission_type,
        filename=file.filename,
        extracted_text=text,
        word_count=word_count,
        version_number=version,
        review_status="running",
        created_at=now,
    )
    db.add(sub)
    await db.commit()
    await db.refresh(sub)

    background_tasks.add_task(_review_task, sub.id)
    return {"submission_id": sub.id, "version_number": version, "word_count": word_count}


@app.get("/api/submissions/{submission_id}")
async def get_submission(submission_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Submission).where(Submission.id == submission_id))
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(404, "Not found")

    rev_r = await db.execute(select(Review).where(Review.submission_id == submission_id))
    rev = rev_r.scalar_one_or_none()

    return {
        "id": sub.id, "user_id": sub.user_id,
        "submission_type": sub.submission_type,
        "filename": sub.filename, "word_count": sub.word_count,
        "version_number": sub.version_number,
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
            "estimated_pass": rev.estimated_pass,
            "auto_fail_reasons": rev.auto_fail_reasons,
            "flags": rev.flags,
            "strengths": rev.strengths,
            "weaknesses": rev.weaknesses,
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
                "version_number": s.version_number,
                "created_at": s.created_at,
                "estimated_total": rev.estimated_total,
                "estimated_max": rev.estimated_max,
                "estimated_pct": rev.estimated_pct,
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
                estimated_pct=data.get("estimated_pct"),
                estimated_pass=data.get("estimated_pass"),
                auto_fail_reasons=data.get("auto_fail_reasons", []),
                flags=data.get("flags", []),
                strengths=data.get("strengths", []),
                weaknesses=data.get("weaknesses", []),
                reviewed_at=now,
            )
            db.add(rev)
            sub.review_status = "done"
            await db.commit()
        except Exception as e:
            sub.review_status = "error"
            await db.commit()
            raise
