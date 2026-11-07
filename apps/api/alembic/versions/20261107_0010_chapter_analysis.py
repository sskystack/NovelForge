"""Add idempotent chapter analysis records."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261107_0010"
down_revision: str | None = "20261107_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "chapter_analyses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("novel_id", sa.Uuid(), nullable=False),
        sa.Column("chapter_id", sa.Uuid(), nullable=False),
        sa.Column("chapter_version_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(30), server_default="queued", nullable=False),
        sa.Column("summary_candidate", sa.String(), server_default="", nullable=False),
        sa.Column("candidates", json_type, nullable=False),
        sa.Column("proposal_ids", json_type, nullable=False),
        sa.Column("warnings", json_type, nullable=False),
        sa.Column("error_message", sa.String(2000), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["novel_id"], ["novels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["novel_id", "chapter_id"], ["chapters.novel_id", "chapters.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["novel_id", "chapter_version_id"],
            ["chapter_versions.novel_id", "chapter_versions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("novel_id", "chapter_version_id", name="uq_chapter_analysis_version"),
    )
    op.create_index(
        "ix_chapter_analyses_novel_created", "chapter_analyses", ["novel_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_chapter_analyses_novel_created", table_name="chapter_analyses")
    op.drop_table("chapter_analyses")
