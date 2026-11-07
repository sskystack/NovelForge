from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import JSON, ForeignKey, Index, String, UniqueConstraint, func, text
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
