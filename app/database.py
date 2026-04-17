from __future__ import annotations
import os
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
    email: Mapped[str | None] = mapped_column(String(255))
    name: Mapped[str | None] = mapped_column(String(255))
    enrollment_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[int] = mapped_column(BigInteger)


class Submission(Base):
    __tablename__ = "submissions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    submission_type: Mapped[str] = mapped_column(String(20))  # case_summary | case_report
    filename: Mapped[str | None] = mapped_column(String(500))
    extracted_text: Mapped[str | None] = mapped_column(Text)
    word_count: Mapped[int | None] = mapped_column(Integer)
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    review_status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[int] = mapped_column(BigInteger)


class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    section_scores: Mapped[dict | None] = mapped_column(JSON)
    overall_impression_a: Mapped[bool | None] = mapped_column(Boolean)
    overall_impression_a_rationale: Mapped[str | None] = mapped_column(Text)
    overall_impression_b: Mapped[bool | None] = mapped_column(Boolean)
    overall_impression_b_rationale: Mapped[str | None] = mapped_column(Text)
    word_count_estimate: Mapped[int | None] = mapped_column(Integer)
    word_count_pass: Mapped[bool | None] = mapped_column(Boolean)
    word_count_note: Mapped[str | None] = mapped_column(String(255))
    formatting_deductions: Mapped[int] = mapped_column(Integer, default=0)
    formatting_notes: Mapped[list | None] = mapped_column(JSON)
    estimated_total: Mapped[float | None] = mapped_column(Float)
    estimated_max: Mapped[int | None] = mapped_column(Integer)
    estimated_pass_score: Mapped[int | None] = mapped_column(Integer)
    estimated_pct: Mapped[float | None] = mapped_column(Float)
    estimated_pass: Mapped[bool | None] = mapped_column(Boolean)
    auto_fail_reasons: Mapped[list | None] = mapped_column(JSON)
    flags: Mapped[list | None] = mapped_column(JSON)
    strengths: Mapped[list | None] = mapped_column(JSON)
    weaknesses: Mapped[list | None] = mapped_column(JSON)
    reviewed_at: Mapped[int | None] = mapped_column(BigInteger)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
