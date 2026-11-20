from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, ForeignKeyConstraint, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from novelforge.database import Base, UTCDateTime


class ChapterAnalysis(Base):
    __tablename__ = "chapter_analyses"
    __table_args__ = (
        UniqueConstraint("novel_id", "chapter_version_id", name="uq_chapter_analysis_version"),
        ForeignKeyConstraint(
            ["novel_id", "chapter_id"],
            ["chapters.novel_id", "chapters.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["novel_id", "chapter_version_id"],
            ["chapter_versions.novel_id", "chapter_versions.id"],
            ondelete="CASCADE",
        ),
        Index("ix_chapter_analyses_novel_created", "novel_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    novel_id: Mapped[UUID] = mapped_column(
        ForeignKey("novels.id", ondelete="CASCADE"), nullable=False
    )
    chapter_id: Mapped[UUID] = mapped_column(nullable=False)
    chapter_version_id: Mapped[UUID] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued")
    summary_candidate: Mapped[str] = mapped_column(String, nullable=False, default="")
    candidates: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )
    proposal_ids: Mapped[list] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False, default=list
    )
    warnings: Mapped[list] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False, default=list
    )
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )
