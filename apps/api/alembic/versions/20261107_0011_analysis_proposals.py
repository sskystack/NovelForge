"""Add post-chapter analysis proposals."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261107_0011"
down_revision: str | None = "20261107_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "analysis_proposals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("novel_id", sa.Uuid(), nullable=False),
        sa.Column("chapter_id", sa.Uuid(), nullable=False),
        sa.Column("chapter_version_id", sa.Uuid(), nullable=False),
        sa.Column("proposal_type", sa.String(40), nullable=False),
        sa.Column("payload", json_type, nullable=False),
        sa.Column("evidence", json_type, nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["novel_id"], ["novels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "novel_id",
            "chapter_version_id",
            "proposal_type",
            "fingerprint",
            name="uq_analysis_proposal_fingerprint",
        ),
    )


def downgrade() -> None:
    op.drop_table("analysis_proposals")
