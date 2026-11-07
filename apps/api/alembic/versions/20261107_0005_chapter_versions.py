"""Add immutable chapter versions.

Revision ID: 20261107_0005
Revises: 20261107_0004
Create Date: 2026-11-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261107_0005"
down_revision: str | None = "20261107_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
content_format = sa.Enum(
    "tiptap",
    "markdown",
    name="content_format",
    native_enum=False,
    create_constraint=True,
)


def upgrade() -> None:
    op.create_table(
        "chapter_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("novel_id", sa.Uuid(), nullable=False),
        sa.Column("chapter_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content_format", content_format, nullable=False),
        sa.Column("tiptap_json", json_type, nullable=True),
        sa.Column("markdown", sa.String(), nullable=True),
        sa.Column("plain_text", sa.String(), server_default="", nullable=False),
        sa.Column("word_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "(content_format = 'tiptap' AND tiptap_json IS NOT NULL AND markdown IS NULL) "
            "OR (content_format = 'markdown' AND markdown IS NOT NULL AND tiptap_json IS NULL)",
            name="ck_chapter_version_content_format",
        ),
        sa.ForeignKeyConstraint(["novel_id"], ["novels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["novel_id", "chapter_id"],
            ["chapters.novel_id", "chapters.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("novel_id", "id", name="uq_chapter_versions_novel_id"),
        sa.UniqueConstraint(
            "novel_id", "chapter_id", "version_number", name="uq_chapter_version_number"
        ),
    )
    op.create_index(
        "ix_chapter_versions_history",
        "chapter_versions",
        ["novel_id", "chapter_id", "version_number"],
    )


def downgrade() -> None:
    op.drop_index("ix_chapter_versions_history", table_name="chapter_versions")
    op.drop_table("chapter_versions")
