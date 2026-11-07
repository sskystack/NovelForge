from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Enum as SqlEnum
from sqlalchemy import (
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from novelforge.database import Base, UTCDateTime

json_type = JSON().with_variant(JSONB, "postgresql")


class KnowledgeStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class KnowledgeVisibility(StrEnum):
    APPROVED = "approved"
    DRAFT = "draft"
    PRIVATE = "private"


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        UniqueConstraint("novel_id", "id", name="uq_knowledge_documents_novel_id"),
        UniqueConstraint(
            "novel_id",
            "source_type",
            "source_id",
            "source_revision",
            name="uq_knowledge_source_revision",
        ),
        Index("ix_knowledge_docs_source", "novel_id", "source_type", "source_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    novel_id: Mapped[UUID] = mapped_column(
        ForeignKey("novels.id", ondelete="CASCADE"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_id: Mapped[UUID | None] = mapped_column(nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    visibility: Mapped[KnowledgeVisibility] = mapped_column(
        SqlEnum(
            KnowledgeVisibility,
            name="knowledge_visibility",
            native_enum=False,
            values_callable=lambda values: [v.value for v in values],
        ),
        nullable=False,
        default=KnowledgeVisibility.APPROVED,
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    chunker_version: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[KnowledgeStatus] = mapped_column(
        SqlEnum(
            KnowledgeStatus,
            name="knowledge_status",
            native_enum=False,
            values_callable=lambda values: [v.value for v in values],
        ),
        nullable=False,
        default=KnowledgeStatus.PENDING,
    )
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["novel_id", "document_id"],
            ["knowledge_documents.novel_id", "knowledge_documents.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("document_id", "chunk_index", name="uq_knowledge_chunk_index"),
        Index("ix_knowledge_chunks_novel_active", "novel_id", "is_active"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    novel_id: Mapped[UUID] = mapped_column(
        ForeignKey("novels.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[UUID] = mapped_column(nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(String, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata", json_type, nullable=False, default=dict
    )
    embedding: Mapped[list[float] | None] = mapped_column(json_type, nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now()
    )
