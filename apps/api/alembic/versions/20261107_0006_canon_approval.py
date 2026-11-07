"""Add canon proposals and immutable revisions.

Revision ID: 20261107_0006
Revises: 20261107_0005
Create Date: 2026-11-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261107_0006"
down_revision: str | None = "20261107_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
proposal_status = sa.Enum(
    "pending",
    "approved",
    "rejected",
    name="proposal_status",
    native_enum=False,
    create_constraint=True,
)


def upgrade() -> None:
    op.create_table(
        "canon_proposals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("novel_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("proposed_data", json_type, nullable=False),
        sa.Column("rationale", sa.String(), server_default="", nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("status", proposal_status, server_default="pending", nullable=False),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["novel_id"], ["novels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("novel_id", "id", name="uq_canon_proposals_novel_id"),
    )
    op.create_index(
        "ix_canon_proposals_status", "canon_proposals", ["novel_id", "status", "created_at"]
    )
    op.create_table(
        "canon_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("novel_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("before_data", json_type, nullable=True),
        sa.Column("after_data", json_type, nullable=False),
        sa.Column("change_reason", sa.String(), server_default="", nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("source_proposal_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["novel_id"], ["novels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["novel_id", "source_proposal_id"],
            ["canon_proposals.novel_id", "canon_proposals.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "novel_id",
            "entity_type",
            "entity_id",
            "revision_number",
            name="uq_canon_revision_number",
        ),
    )
    op.create_index(
        "ix_canon_revisions_entity",
        "canon_revisions",
        ["novel_id", "entity_type", "entity_id", "revision_number"],
    )


def downgrade() -> None:
    op.drop_index("ix_canon_revisions_entity", table_name="canon_revisions")
    op.drop_table("canon_revisions")
    op.drop_index("ix_canon_proposals_status", table_name="canon_proposals")
    op.drop_table("canon_proposals")
