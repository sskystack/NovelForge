"""Add nested outlines and chapter metadata.

Revision ID: 20261107_0004
Revises: 20261107_0003
Create Date: 2026-11-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261107_0004"
down_revision: str | None = "20261107_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
outline_node_type = sa.Enum(
    "book",
    "volume",
    "arc",
    "chapter",
    "scene",
    "beat",
    name="outline_node_type",
    native_enum=False,
    create_constraint=True,
)
chapter_status = sa.Enum(
    "planned",
    "draft",
    "in_progress",
    "review",
    "completed",
    name="chapter_status",
    native_enum=False,
    create_constraint=True,
)


def upgrade() -> None:
    op.create_table(
        "outline_nodes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("novel_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("node_type", outline_node_type, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("synopsis", sa.String(), server_default="", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("planned_start_order", sa.Numeric(20, 6), nullable=True),
        sa.Column("planned_end_order", sa.Numeric(20, 6), nullable=True),
        sa.Column("status", sa.String(length=40), server_default="planned", nullable=False),
        sa.Column("linked_entity_ids", json_type, server_default=sa.text("'[]'"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["novel_id"], ["novels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["novel_id", "parent_id"],
            ["outline_nodes.novel_id", "outline_nodes.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("novel_id", "id", name="uq_outline_nodes_novel_id"),
    )
    op.create_index(
        "ix_outline_parent_order", "outline_nodes", ["novel_id", "parent_id", "sort_order"]
    )

    op.create_table(
        "chapters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("novel_id", sa.Uuid(), nullable=False),
        sa.Column("outline_node_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("chapter_number", sa.Integer(), nullable=True),
        sa.Column("story_order", sa.Numeric(20, 6), nullable=True),
        sa.Column("status", chapter_status, server_default="planned", nullable=False),
        sa.Column("current_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("summary", sa.String(), server_default="", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["novel_id"], ["novels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["novel_id", "outline_node_id"],
            ["outline_nodes.novel_id", "outline_nodes.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("novel_id", "id", name="uq_chapters_novel_id"),
    )
    op.create_index("ix_chapters_order", "chapters", ["novel_id", "chapter_number"])
    op.create_index("ix_chapters_story_order", "chapters", ["novel_id", "story_order"])


def downgrade() -> None:
    op.drop_index("ix_chapters_story_order", table_name="chapters")
    op.drop_index("ix_chapters_order", table_name="chapters")
    op.drop_table("chapters")
    op.drop_index("ix_outline_parent_order", table_name="outline_nodes")
    op.drop_table("outline_nodes")
