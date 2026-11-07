"""Add scoped tool call audit records."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261107_0008"
down_revision: str | None = "20261107_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tool_call_audits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("novel_id", sa.Uuid(), nullable=False),
        sa.Column("generation_id", sa.Uuid(), nullable=True),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("duration_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column("input_summary", sa.String(2000), server_default="", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["novel_id"], ["novels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tool_call_audits_generation",
        "tool_call_audits",
        ["novel_id", "generation_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_tool_call_audits_generation", table_name="tool_call_audits")
    op.drop_table("tool_call_audits")
