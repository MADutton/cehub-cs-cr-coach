from __future__ import annotations
import os
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text, Integer, Float, Boolean, BigInteger, JSON

_raw = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./coach.db")
if _raw.startswith("postgres://"):
    _raw = _raw.replace("postgres://", "postgresql+asyncpg://", 1)
elif _raw.startswith("postgresql://"):
    _raw = _raw.replace("postgresql://", "postgresql+asyncpg://", 1)
DATABASE_URL = _raw

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    thinkific_user_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255))
    name: Mapped[Optional[str]] = mapped_column(String(255))
    enrollment_id: Mapped[Optional[str]] = mapped_column(String(255))
    user_hash: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    created_at: Mapped[int] = mapped_column(BigInteger)


class Submission(Base):
    __tablename__ = "submissions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_uuid: Mapped[Optional[str]] = mapped_column(String(36), unique=True, index=True)
    rmv_type: Mapped[str] = mapped_column(String(32), default="case_review")
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    enrollment_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    submission_type: Mapped[str] = mapped_column(String(20))
    filename: Mapped[Optional[str]] = mapped_column(String(500))
    extracted_text: Mapped[Optional[str]] = mapped_column(Text)
    word_count: Mapped[Optional[int]] = mapped_column(Integer)
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    review_status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[int] = mapped_column(BigInteger)


class Enrollment(Base):
    __tablename__ = "enrollments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    thinkific_enrollment_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    thinkific_user_id: Mapped[str] = mapped_column(String(255), index=True)
    course_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    user_email: Mapped[Optional[str]] = mapped_column(String(255))
    user_name: Mapped[Optional[str]] = mapped_column(String(255))
    expiry_date: Mapped[Optional[str]] = mapped_column(String(64))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[int] = mapped_column(BigInteger)
    updated_at: Mapped[int] = mapped_column(BigInteger)


class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    section_scores: Mapped[Optional[dict]] = mapped_column(JSON)
    overall_impression_a: Mapped[Optional[bool]] = mapped_column(Boolean)
    overall_impression_a_rationale: Mapped[Optional[str]] = mapped_column(Text)
    overall_impression_b: Mapped[Optional[bool]] = mapped_column(Boolean)
    overall_impression_b_rationale: Mapped[Optional[str]] = mapped_column(Text)
    word_count_estimate: Mapped[Optional[int]] = mapped_column(Integer)
    word_count_pass: Mapped[Optional[bool]] = mapped_column(Boolean)
    word_count_note: Mapped[Optional[str]] = mapped_column(String(255))
    formatting_deductions: Mapped[int] = mapped_column(Integer, default=0)
    formatting_notes: Mapped[Optional[list]] = mapped_column(JSON)
    estimated_total: Mapped[Optional[float]] = mapped_column(Float)
    estimated_max: Mapped[Optional[int]] = mapped_column(Integer)
    estimated_pass_score: Mapped[Optional[int]] = mapped_column(Integer)
    estimated_pct: Mapped[Optional[float]] = mapped_column(Float)
    previous_pct: Mapped[Optional[float]] = mapped_column(Float)
    score_delta: Mapped[Optional[float]] = mapped_column(Float)
    estimated_pass: Mapped[Optional[bool]] = mapped_column(Boolean)
    auto_fail_reasons: Mapped[Optional[list]] = mapped_column(JSON)
    flags: Mapped[Optional[list]] = mapped_column(JSON)
    strengths: Mapped[Optional[list]] = mapped_column(JSON)
    weaknesses: Mapped[Optional[list]] = mapped_column(JSON)
    model_version: Mapped[Optional[str]] = mapped_column(String(100))
    reviewed_at: Mapped[Optional[int]] = mapped_column(BigInteger)


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_uuid: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    submission_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    submission_uuid: Mapped[Optional[str]] = mapped_column(String(36), index=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[int] = mapped_column(BigInteger)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

