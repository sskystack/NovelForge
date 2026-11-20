"""Add generation sessions."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261107_0009"
down_revision: str | None = "20261107_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "generation_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("novel_id", sa.Uuid(), nullable=False),
        sa.Column("chapter_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("task_profile", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), server_default="queued", nullable=False),
        sa.Column("instructions", sa.String(20000), server_default="", nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("context_snapshot", json_type, nullable=False),
        sa.Column("output", json_type, nullable=False),
        sa.Column("error_message", sa.String(2000), nullable=True),
        sa.Column("expected_version", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["novel_id"], ["novels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_generation_sessions_novel_created", "generation_sessions", ["novel_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_generation_sessions_novel_created", table_name="generation_sessions")
    op.drop_table("generation_sessions")
