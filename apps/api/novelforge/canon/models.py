from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from novelforge.database import Base, UTCDateTime

json_type = JSON().with_variant(JSONB, "postgresql")


class CanonStatus(StrEnum):
    DRAFT = "draft"
    PROPOSED = "proposed"
    CANON = "canon"
    DEPRECATED = "deprecated"


canon_status_type = SqlEnum(
    CanonStatus,
    name="canon_status",
    native_enum=False,
    create_constraint=True,
    values_callable=lambda values: [value.value for value in values],
)


class NovelOwnedCanon:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    novel_id: Mapped[UUID] = mapped_column(
        ForeignKey("novels.id", ondelete="CASCADE"), nullable=False
    )
    canon_status: Mapped[CanonStatus] = mapped_column(
        canon_status_type, nullable=False, default=CanonStatus.DRAFT, server_default="draft"
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Character(NovelOwnedCanon, Base):
    __tablename__ = "characters"
    __table_args__ = (
        UniqueConstraint("novel_id", "id", name="uq_characters_novel_id"),
        Index("ix_characters_novel_name", "novel_id", "name"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(
        json_type, nullable=False, default=list, server_default=text("'[]'")
    )
    summary: Mapped[str] = mapped_column(String, nullable=False, default="", server_default="")
    personality: Mapped[dict[str, object]] = mapped_column(
        json_type, nullable=False, default=dict, server_default=text("'{}'")
    )
    background: Mapped[str] = mapped_column(String, nullable=False, default="", server_default="")
    goals: Mapped[list[str]] = mapped_column(
        json_type, nullable=False, default=list, server_default=text("'[]'")
    )
    constraints: Mapped[list[str]] = mapped_column(
        json_type, nullable=False, default=list, server_default=text("'[]'")
    )
    attributes: Mapped[dict[str, object]] = mapped_column(
        json_type, nullable=False, default=dict, server_default=text("'{}'")
    )


class Location(NovelOwnedCanon, Base):
    __tablename__ = "locations"
    __table_args__ = (
        UniqueConstraint("novel_id", "id", name="uq_locations_novel_id"),
        Index("ix_locations_novel_name", "novel_id", "name"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False, default="", server_default="")
    attributes: Mapped[dict[str, object]] = mapped_column(
        json_type, nullable=False, default=dict, server_default=text("'{}'")
    )


class Faction(NovelOwnedCanon, Base):
    __tablename__ = "factions"
    __table_args__ = (
        UniqueConstraint("novel_id", "id", name="uq_factions_novel_id"),
        Index("ix_factions_novel_name", "novel_id", "name"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False, default="", server_default="")
    attributes: Mapped[dict[str, object]] = mapped_column(
        json_type, nullable=False, default=dict, server_default=text("'{}'")
    )


class WorldRule(NovelOwnedCanon, Base):
    __tablename__ = "world_rules"
    __table_args__ = (
        UniqueConstraint("novel_id", "id", name="uq_world_rules_novel_id"),
        Index("ix_world_rules_novel_category", "novel_id", "category"),
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(
        String(80), nullable=False, default="general", server_default="general"
    )
    description: Mapped[str] = mapped_column(String, nullable=False)
    constraints: Mapped[dict[str, object]] = mapped_column(
        json_type, nullable=False, default=dict, server_default=text("'{}'")
    )


class StoryEvent(Base):
    __tablename__ = "story_events"
    __table_args__ = (
        UniqueConstraint("novel_id", "id", name="uq_story_events_novel_id"),
        Index("ix_story_events_order", "novel_id", "story_order"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    novel_id: Mapped[UUID] = mapped_column(
        ForeignKey("novels.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False, default="", server_default="")
    story_order: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)
    story_time_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_chapter_id: Mapped[UUID | None] = mapped_column(nullable=True)
    event_type: Mapped[str] = mapped_column(
        String(80), nullable=False, default="general", server_default="general"
    )
    canon_status: Mapped[CanonStatus] = mapped_column(
        canon_status_type, nullable=False, default=CanonStatus.DRAFT, server_default="draft"
    )
    occurred_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CharacterState(Base):
    __tablename__ = "character_states"
    __table_args__ = (
        UniqueConstraint("novel_id", "id", name="uq_character_states_novel_id"),
        ForeignKeyConstraint(
            ["novel_id", "character_id"],
            ["characters.novel_id", "characters.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["novel_id", "source_event_id"],
            ["story_events.novel_id", "story_events.id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "valid_to_order IS NULL OR valid_to_order > story_order",
            name="ck_character_states_valid_interval",
        ),
        Index("ix_character_states_lookup", "novel_id", "character_id", "story_order"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    novel_id: Mapped[UUID] = mapped_column(
        ForeignKey("novels.id", ondelete="CASCADE"), nullable=False
    )
    character_id: Mapped[UUID] = mapped_column(nullable=False)
    story_order: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    valid_to_order: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    state: Mapped[dict[str, object]] = mapped_column(json_type, nullable=False)
    source_event_id: Mapped[UUID | None] = mapped_column(nullable=True)
    canon_status: Mapped[CanonStatus] = mapped_column(
        canon_status_type, nullable=False, default=CanonStatus.PROPOSED, server_default="proposed"
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now()
    )


class Relationship(Base):
    __tablename__ = "relationships"
    __table_args__ = (
        ForeignKeyConstraint(
            ["novel_id", "from_character_id"],
            ["characters.novel_id", "characters.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["novel_id", "to_character_id"],
            ["characters.novel_id", "characters.id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("from_character_id <> to_character_id", name="ck_relationships_distinct"),
        CheckConstraint(
            "valid_to_order IS NULL OR valid_from_order IS NULL "
            "OR valid_to_order > valid_from_order",
            name="ck_relationships_valid_interval",
        ),
        Index("ix_relationships_from", "novel_id", "from_character_id"),
        Index("ix_relationships_to", "novel_id", "to_character_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    novel_id: Mapped[UUID] = mapped_column(
        ForeignKey("novels.id", ondelete="CASCADE"), nullable=False
    )
    from_character_id: Mapped[UUID] = mapped_column(nullable=False)
    to_character_id: Mapped[UUID] = mapped_column(nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False, default="", server_default="")
    valid_from_order: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    valid_to_order: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    canon_status: Mapped[CanonStatus] = mapped_column(
        canon_status_type, nullable=False, default=CanonStatus.DRAFT, server_default="draft"
    )
    attributes: Mapped[dict[str, object]] = mapped_column(
        json_type, nullable=False, default=dict, server_default=text("'{}'")
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )
