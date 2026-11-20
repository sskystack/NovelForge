from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CharacterLookup(ToolInput):
    query: NonEmpty
    limit: int = Field(default=10, ge=1, le=50)


class WorldbuildingLookup(ToolInput):
    entity_type: Literal["character", "location", "faction", "world_rule"]
    query: NonEmpty = "*"
    limit: int = Field(default=10, ge=1, le=50)


class TimelineLookup(ToolInput):
    story_order_from: float | None = Field(default=None, ge=0)
    story_order_to: float | None = Field(default=None, ge=0)
    query: str = Field(default="", max_length=4000)
    limit: int = Field(default=30, ge=1, le=100)


class OutlineLookup(ToolInput):
    query: str = Field(default="", max_length=4000)
    limit: int = Field(default=50, ge=1, le=200)


class ChapterSearch(ToolInput):
    query: NonEmpty
    limit: int = Field(default=10, ge=1, le=50)


class OutlineDraft(ToolInput):
    parent_id: UUID | None = None
    node_type: Literal["book", "volume", "arc", "chapter", "scene", "beat"]
    title: NonEmpty
    synopsis: str = Field(default="", max_length=50_000)
    sort_order: int = 0


class SummaryDraft(ToolInput):
    chapter_id: UUID
    summary: NonEmpty


class CanonProposalInput(ToolInput):
    entity_type: Literal[
        "character",
        "location",
        "faction",
        "world_rule",
        "story_event",
        "character_state",
        "relationship",
    ]
    entity_id: UUID | None = None
    proposed_data: dict[str, object]
    rationale: str = Field(default="", max_length=20_000)
