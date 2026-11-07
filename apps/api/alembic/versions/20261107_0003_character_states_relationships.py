"""Add story events, character states and relationships.

Revision ID: 20261107_0003
Revises: 20261107_0002
Create Date: 2026-11-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261107_0003"
down_revision: str | None = "20261107_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
canon_status = sa.Enum(
    "draft",
    "proposed",
    "canon",
    "deprecated",
    name="canon_status",
    native_enum=False,
    create_constraint=True,
)


def upgrade() -> None:
    op.create_table(
        "story_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("novel_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(), server_default="", nullable=False),
        sa.Column("story_order", sa.Numeric(20, 6), nullable=False),
        sa.Column("story_time_label", sa.String(length=120), nullable=True),
        sa.Column("source_chapter_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=80), server_default="general", nullable=False),
        sa.Column("canon_status", canon_status, server_default="draft", nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["novel_id"], ["novels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("novel_id", "id", name="uq_story_events_novel_id"),
    )
    op.create_index("ix_story_events_order", "story_events", ["novel_id", "story_order"])

    op.create_table(
        "character_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("novel_id", sa.Uuid(), nullable=False),
        sa.Column("character_id", sa.Uuid(), nullable=False),
        sa.Column("story_order", sa.Numeric(20, 6), nullable=False),
        sa.Column("valid_to_order", sa.Numeric(20, 6), nullable=True),
        sa.Column("state", json_type, nullable=False),
        sa.Column("source_event_id", sa.Uuid(), nullable=True),
        sa.Column("canon_status", canon_status, server_default="proposed", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "valid_to_order IS NULL OR valid_to_order > story_order",
            name="ck_character_states_valid_interval",
        ),
        sa.ForeignKeyConstraint(["novel_id"], ["novels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["novel_id", "character_id"],
            ["characters.novel_id", "characters.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["novel_id", "source_event_id"],
            ["story_events.novel_id", "story_events.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("novel_id", "id", name="uq_character_states_novel_id"),
    )
    op.create_index(
        "ix_character_states_lookup",
        "character_states",
        ["novel_id", "character_id", "story_order"],
    )

    op.create_table(
        "relationships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("novel_id", sa.Uuid(), nullable=False),
        sa.Column("from_character_id", sa.Uuid(), nullable=False),
        sa.Column("to_character_id", sa.Uuid(), nullable=False),
        sa.Column("relationship_type", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(), server_default="", nullable=False),
        sa.Column("valid_from_order", sa.Numeric(20, 6), nullable=True),
        sa.Column("valid_to_order", sa.Numeric(20, 6), nullable=True),
        sa.Column("canon_status", canon_status, server_default="draft", nullable=False),
        sa.Column("attributes", json_type, server_default=sa.text("'{}'"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "from_character_id <> to_character_id", name="ck_relationships_distinct"
        ),
        sa.CheckConstraint(
            "valid_to_order IS NULL OR valid_from_order IS NULL "
            "OR valid_to_order > valid_from_order",
            name="ck_relationships_valid_interval",
        ),
        sa.ForeignKeyConstraint(["novel_id"], ["novels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["novel_id", "from_character_id"],
            ["characters.novel_id", "characters.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["novel_id", "to_character_id"],
            ["characters.novel_id", "characters.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_relationships_from", "relationships", ["novel_id", "from_character_id"])
    op.create_index("ix_relationships_to", "relationships", ["novel_id", "to_character_id"])


def downgrade() -> None:
    op.drop_index("ix_relationships_to", table_name="relationships")
    op.drop_index("ix_relationships_from", table_name="relationships")
    op.drop_table("relationships")
    op.drop_index("ix_character_states_lookup", table_name="character_states")
    op.drop_table("character_states")
    op.drop_index("ix_story_events_order", table_name="story_events")
    op.drop_table("story_events")
