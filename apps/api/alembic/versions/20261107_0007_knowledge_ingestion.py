"""Add novel-scoped knowledge documents and chunks.

Revision ID: 20261107_0007
Revises: 20261107_0006
Create Date: 2026-11-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261107_0007"
down_revision: str | None = "20261107_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
visibility_type = sa.Enum(
    "approved",
    "draft",
    "private",
    name="knowledge_visibility",
    native_enum=False,
    create_constraint=True,
)
status_type = sa.Enum(
    "pending",
    "processing",
    "ready",
    "failed",
    name="knowledge_status",
    native_enum=False,
    create_constraint=True,
)


def upgrade() -> None:
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("novel_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("source_revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("visibility", visibility_type, server_default="approved", nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("chunker_version", sa.String(length=40), nullable=False),
        sa.Column("status", status_type, server_default="pending", nullable=False),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["novel_id"], ["novels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("novel_id", "id", name="uq_knowledge_documents_novel_id"),
        sa.UniqueConstraint(
            "novel_id",
            "source_type",
            "source_id",
            "source_revision",
            name="uq_knowledge_source_revision",
        ),
    )
    op.create_index(
        "ix_knowledge_docs_source", "knowledge_documents", ["novel_id", "source_type", "source_id"]
    )
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("novel_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("token_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("metadata", json_type, nullable=False),
        sa.Column("embedding", json_type, nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["novel_id"], ["novels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["novel_id", "document_id"],
            ["knowledge_documents.novel_id", "knowledge_documents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_knowledge_chunk_index"),
    )
    op.create_index(
        "ix_knowledge_chunks_novel_active", "knowledge_chunks", ["novel_id", "is_active"]
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_chunks_novel_active", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.drop_index("ix_knowledge_docs_source", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
