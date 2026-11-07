"""Add novel-scoped canon entities.

Revision ID: 20261107_0002
Revises: 20261107_0001
Create Date: 2026-11-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261107_0002"
down_revision: str | None = "20261107_0001"
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


def _common_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("novel_id", sa.Uuid(), nullable=False),
        sa.Column("canon_status", canon_status, server_default="draft", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def _create_entity_table(
    table_name: str,
    columns: list[sa.Column],
    index_name: str,
    index_columns: list[str],
) -> None:
    op.create_table(
        table_name,
        *_common_columns(),
        *columns,
        sa.ForeignKeyConstraint(["novel_id"], ["novels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("novel_id", "id", name=f"uq_{table_name}_novel_id"),
    )
    op.create_index(index_name, table_name, index_columns)


def upgrade() -> None:
    _create_entity_table(
        "characters",
        [
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("aliases", json_type, server_default=sa.text("'[]'"), nullable=False),
            sa.Column("summary", sa.String(), server_default="", nullable=False),
            sa.Column("personality", json_type, server_default=sa.text("'{}'"), nullable=False),
            sa.Column("background", sa.String(), server_default="", nullable=False),
            sa.Column("goals", json_type, server_default=sa.text("'[]'"), nullable=False),
            sa.Column("constraints", json_type, server_default=sa.text("'[]'"), nullable=False),
            sa.Column("attributes", json_type, server_default=sa.text("'{}'"), nullable=False),
        ],
        "ix_characters_novel_name",
        ["novel_id", "name"],
    )
    _create_entity_table(
        "locations",
        [
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("description", sa.String(), server_default="", nullable=False),
            sa.Column("attributes", json_type, server_default=sa.text("'{}'"), nullable=False),
        ],
        "ix_locations_novel_name",
        ["novel_id", "name"],
    )
    _create_entity_table(
        "factions",
        [
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("description", sa.String(), server_default="", nullable=False),
            sa.Column("attributes", json_type, server_default=sa.text("'{}'"), nullable=False),
        ],
        "ix_factions_novel_name",
        ["novel_id", "name"],
    )
    _create_entity_table(
        "world_rules",
        [
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("category", sa.String(length=80), server_default="general", nullable=False),
            sa.Column("description", sa.String(), nullable=False),
            sa.Column("constraints", json_type, server_default=sa.text("'{}'"), nullable=False),
        ],
        "ix_world_rules_novel_category",
        ["novel_id", "category"],
    )


def downgrade() -> None:
    op.drop_index("ix_world_rules_novel_category", table_name="world_rules")
    op.drop_table("world_rules")
    op.drop_index("ix_factions_novel_name", table_name="factions")
    op.drop_table("factions")
    op.drop_index("ix_locations_novel_name", table_name="locations")
    op.drop_table("locations")
    op.drop_index("ix_characters_novel_name", table_name="characters")
    op.drop_table("characters")
