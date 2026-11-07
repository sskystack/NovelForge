"""Add deterministic consistency issues."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261107_0012"
down_revision: str | None = "20261107_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "consistency_issues",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("novel_id", sa.Uuid(), nullable=False),
        sa.Column("issue_type", sa.String(60), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("evidence", json_type, nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(30), server_default="open", nullable=False),
        sa.Column("resolved_by", sa.Uuid(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["novel_id"], ["novels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("novel_id", "fingerprint", name="uq_consistency_issue_fingerprint"),
    )
    op.create_index(
        "ix_consistency_issues_novel_status",
        "consistency_issues",
        ["novel_id", "status", "severity"],
    )


def downgrade() -> None:
    op.drop_index("ix_consistency_issues_novel_status", table_name="consistency_issues")
    op.drop_table("consistency_issues")
