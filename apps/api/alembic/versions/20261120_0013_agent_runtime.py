"""Persist local agent runs, author configuration and MCP registrations."""

import sqlalchemy as sa

from alembic import op

revision = "20261120_0013"
down_revision = "20261107_0012"
branch_labels = None
depends_on = None


def upgrade():
    from novelforge.knowledge.fts import create_index

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "novel_id", sa.Uuid(), sa.ForeignKey("novels.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("prompt", sa.String(20000), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("output", sa.String(), nullable=False),
        sa.Column("error", sa.String(2000), nullable=True),
        sa.Column("limits", sa.JSON(), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("messages", sa.JSON(), nullable=False),
        sa.Column("tokens_used", sa.Integer(), nullable=False),
        sa.Column("tools_used", sa.Integer(), nullable=False),
        sa.Column("rounds_used", sa.Integer(), nullable=False),
        sa.Column("elapsed_seconds", sa.Float(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_agent_runs_owner_novel", "agent_runs", ["owner_id", "novel_id"])
    op.create_table(
        "agent_steps",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "run_id", sa.Uuid(), sa.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("tool_name", sa.String(200), nullable=True),
        sa.Column("tool_call_id", sa.String(200), nullable=True),
        sa.Column("arguments", sa.JSON(), nullable=False),
        sa.Column("arguments_hash", sa.String(64), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("error", sa.String(2000), nullable=True),
        sa.Column("decision", sa.Boolean(), nullable=True),
        sa.Column("decided_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("run_id", "sequence", name="uq_agent_step_sequence"),
        sa.UniqueConstraint("run_id", "tool_call_id", name="uq_agent_step_tool_call"),
    )
    op.create_table(
        "local_ai_configs",
        sa.Column(
            "owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("configuration", sa.JSON(), nullable=False),
    )
    op.create_table(
        "mcp_servers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("last_error", sa.String(1000), nullable=True),
    )
    create_index(op.get_bind())


def downgrade():
    from novelforge.knowledge.fts import drop_index

    drop_index(op.get_bind())
    op.drop_table("mcp_servers")
    op.drop_table("local_ai_configs")
    op.drop_table("agent_steps")
    op.drop_index("ix_agent_runs_owner_novel", table_name="agent_runs")
    op.drop_table("agent_runs")
