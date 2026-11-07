from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from novelforge.database import Base, UTCDateTime


class GenerationStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ACCEPTED = "accepted"


class TaskProfile(StrEnum):
    OUTLINE = "outline"
    WRITING = "writing"
    SUMMARY = "summary"
    CRITIQUE = "critique"


class GenerationSession(Base):
    __tablename__ = "generation_sessions"
    __table_args__ = (Index("ix_generation_sessions_novel_created", "novel_id", "created_at"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    novel_id: Mapped[UUID] = mapped_column(
        ForeignKey("novels.id", ondelete="CASCADE"), nullable=False
    )
    chapter_id: Mapped[UUID | None] = mapped_column(nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    task_profile: Mapped[TaskProfile] = mapped_column(String(30), nullable=False)
    status: Mapped[GenerationStatus] = mapped_column(
        String(30), nullable=False, default=GenerationStatus.QUEUED
    )
    instructions: Mapped[str] = mapped_column(String(20_000), nullable=False, default="")
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    context_snapshot: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )
    output: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    expected_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )
