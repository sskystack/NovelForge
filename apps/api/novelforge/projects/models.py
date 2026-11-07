from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import JSON, ForeignKey, Index, String, func, text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from novelforge.database import Base, UTCDateTime

if TYPE_CHECKING:
    from novelforge.identity.models import User


class NovelStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


json_type = JSON().with_variant(JSONB, "postgresql")
novel_status_type = SqlEnum(
    NovelStatus,
    name="novel_status",
    native_enum=False,
    create_constraint=True,
    values_callable=lambda values: [value.value for value in values],
)


class Novel(Base):
    __tablename__ = "novels"
    __table_args__ = (Index("ix_novels_owner_status", "owner_user_id", "status"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    language: Mapped[str] = mapped_column(String(32), nullable=False, default="zh-CN")
    genre: Mapped[list[str]] = mapped_column(
        json_type, nullable=False, default=list, server_default=text("'[]'")
    )
    premise: Mapped[str] = mapped_column(String, nullable=False, default="", server_default="")
    writing_preferences: Mapped[dict[str, object]] = mapped_column(
        json_type, nullable=False, default=dict, server_default=text("'{}'")
    )
    status: Mapped[NovelStatus] = mapped_column(
        novel_status_type, nullable=False, default=NovelStatus.ACTIVE, server_default="active"
    )
    settings: Mapped[dict[str, object]] = mapped_column(
        json_type, nullable=False, default=dict, server_default=text("'{}'")
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    archived_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    owner: Mapped[User] = relationship(back_populates="novels")
