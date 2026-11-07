from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    event,
    func,
    text,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import Mapped, mapped_column

from novelforge.database import Base, UTCDateTime

json_type = JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql")


class OutlineNodeType(StrEnum):
    BOOK = "book"
    VOLUME = "volume"
    ARC = "arc"
    CHAPTER = "chapter"
    SCENE = "scene"
    BEAT = "beat"


class ChapterStatus(StrEnum):
    PLANNED = "planned"
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    COMPLETED = "completed"


class ContentFormat(StrEnum):
    TIPTAP = "tiptap"
    MARKDOWN = "markdown"


outline_node_type = SqlEnum(
    OutlineNodeType,
    name="outline_node_type",
    native_enum=False,
    create_constraint=True,
    values_callable=lambda values: [value.value for value in values],
)
chapter_status_type = SqlEnum(
    ChapterStatus,
    name="chapter_status",
    native_enum=False,
    create_constraint=True,
    values_callable=lambda values: [value.value for value in values],
)
content_format_type = SqlEnum(
    ContentFormat,
    name="content_format",
    native_enum=False,
    create_constraint=True,
    values_callable=lambda values: [value.value for value in values],
)


class OutlineNode(Base):
    __tablename__ = "outline_nodes"
    __table_args__ = (
        UniqueConstraint("novel_id", "id", name="uq_outline_nodes_novel_id"),
        ForeignKeyConstraint(
            ["novel_id", "parent_id"],
            ["outline_nodes.novel_id", "outline_nodes.id"],
            ondelete="CASCADE",
        ),
        Index("ix_outline_parent_order", "novel_id", "parent_id", "sort_order"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    novel_id: Mapped[UUID] = mapped_column(
        ForeignKey("novels.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[UUID | None] = mapped_column(nullable=True)
    node_type: Mapped[OutlineNodeType] = mapped_column(outline_node_type, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    synopsis: Mapped[str] = mapped_column(String, nullable=False, default="", server_default="")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    planned_start_order: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    planned_end_order: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="planned", server_default="planned"
    )
    linked_entity_ids: Mapped[list[UUID]] = mapped_column(
        json_type, nullable=False, default=list, server_default=text("'[]'")
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Chapter(Base):
    __tablename__ = "chapters"
    __table_args__ = (
        UniqueConstraint("novel_id", "id", name="uq_chapters_novel_id"),
        ForeignKeyConstraint(
            ["novel_id", "outline_node_id"],
            ["outline_nodes.novel_id", "outline_nodes.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_chapters_order", "novel_id", "chapter_number"),
        Index("ix_chapters_story_order", "novel_id", "story_order"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    novel_id: Mapped[UUID] = mapped_column(
        ForeignKey("novels.id", ondelete="CASCADE"), nullable=False
    )
    outline_node_id: Mapped[UUID | None] = mapped_column(nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    chapter_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    story_order: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    status: Mapped[ChapterStatus] = mapped_column(
        chapter_status_type, nullable=False, default=ChapterStatus.PLANNED, server_default="planned"
    )
    current_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    summary: Mapped[str] = mapped_column(String, nullable=False, default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ChapterVersion(Base):
    __tablename__ = "chapter_versions"
    __table_args__ = (
        UniqueConstraint("novel_id", "id", name="uq_chapter_versions_novel_id"),
        UniqueConstraint(
            "novel_id", "chapter_id", "version_number", name="uq_chapter_version_number"
        ),
        ForeignKeyConstraint(
            ["novel_id", "chapter_id"],
            ["chapters.novel_id", "chapters.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        CheckConstraint(
            "(content_format = 'tiptap' AND tiptap_json IS NOT NULL AND markdown IS NULL) "
            "OR (content_format = 'markdown' AND markdown IS NOT NULL AND tiptap_json IS NULL)",
            name="ck_chapter_version_content_format",
        ),
        Index("ix_chapter_versions_history", "novel_id", "chapter_id", "version_number"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    novel_id: Mapped[UUID] = mapped_column(
        ForeignKey("novels.id", ondelete="CASCADE"), nullable=False
    )
    chapter_id: Mapped[UUID] = mapped_column(nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content_format: Mapped[ContentFormat] = mapped_column(content_format_type, nullable=False)
    tiptap_json: Mapped[dict[str, object] | None] = mapped_column(json_type, nullable=True)
    markdown: Mapped[str | None] = mapped_column(String, nullable=True)
    plain_text: Mapped[str] = mapped_column(String, nullable=False, default="", server_default="")
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_by: Mapped[UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now()
    )


@event.listens_for(ChapterVersion, "before_update")
def prevent_chapter_version_update(_mapper, _connection, _version) -> None:
    raise InvalidRequestError("Chapter versions are immutable.")


@event.listens_for(ChapterVersion, "before_delete")
def prevent_chapter_version_delete(_mapper, _connection, _version) -> None:
    raise InvalidRequestError("Chapter versions are immutable.")
