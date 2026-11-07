from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from novelforge.planning.models import ChapterStatus, ContentFormat, OutlineNodeType

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
NodeStatus = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]


class OutlineNodeCreate(BaseModel):
    parent_id: UUID | None = None
    node_type: OutlineNodeType
    title: Title
    synopsis: str = Field(default="", max_length=50_000)
    sort_order: int = Field(default=0, ge=-2_147_483_648, le=2_147_483_647)
    planned_start_order: Decimal | None = Field(default=None, max_digits=20, decimal_places=6)
    planned_end_order: Decimal | None = Field(default=None, max_digits=20, decimal_places=6)
    status: NodeStatus = "planned"
    linked_entity_ids: list[UUID] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def validate_story_range(self):
        if (
            self.planned_start_order is not None
            and self.planned_end_order is not None
            and self.planned_end_order < self.planned_start_order
        ):
            raise ValueError("planned_end_order cannot precede planned_start_order.")
        return self


class OutlineNodeUpdate(BaseModel):
    parent_id: UUID | None = None
    node_type: OutlineNodeType | None = None
    title: Title | None = None
    synopsis: str | None = Field(default=None, max_length=50_000)
    sort_order: int | None = Field(default=None, ge=-2_147_483_648, le=2_147_483_647)
    planned_start_order: Decimal | None = Field(default=None, max_digits=20, decimal_places=6)
    planned_end_order: Decimal | None = Field(default=None, max_digits=20, decimal_places=6)
    status: NodeStatus | None = None
    linked_entity_ids: list[UUID] | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def validate_patch(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")
        for field in self.model_fields_set:
            if getattr(self, field) is None and field not in {
                "parent_id",
                "planned_start_order",
                "planned_end_order",
            }:
                raise ValueError(f"{field} cannot be null.")
        if (
            self.planned_start_order is not None
            and self.planned_end_order is not None
            and self.planned_end_order < self.planned_start_order
        ):
            raise ValueError("planned_end_order cannot precede planned_start_order.")
        return self


class OutlineNodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    novel_id: UUID
    parent_id: UUID | None
    node_type: OutlineNodeType
    title: str
    synopsis: str
    sort_order: int
    planned_start_order: Decimal | None
    planned_end_order: Decimal | None
    status: str
    linked_entity_ids: list[UUID]
    created_at: datetime
    updated_at: datetime
    children: list["OutlineNodeRead"] = Field(default_factory=list)


class OutlineReorder(BaseModel):
    parent_id: UUID | None = None
    ordered_node_ids: list[UUID] = Field(min_length=1, max_length=500)


class ChapterCreate(BaseModel):
    outline_node_id: UUID | None = None
    title: Title
    chapter_number: int | None = Field(default=None, ge=-2_147_483_648, le=2_147_483_647)
    story_order: Decimal | None = Field(default=None, max_digits=20, decimal_places=6)
    status: ChapterStatus = ChapterStatus.PLANNED
    summary: str = Field(default="", max_length=50_000)


class ChapterUpdate(BaseModel):
    outline_node_id: UUID | None = None
    title: Title | None = None
    chapter_number: int | None = Field(default=None, ge=-2_147_483_648, le=2_147_483_647)
    story_order: Decimal | None = Field(default=None, max_digits=20, decimal_places=6)
    status: ChapterStatus | None = None
    summary: str | None = Field(default=None, max_length=50_000)
    content_format: ContentFormat | None = None
    content: dict[str, object] | None = None
    markdown: str | None = Field(default=None, max_length=2_000_000)

    @model_validator(mode="after")
    def validate_patch(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")
        for field in self.model_fields_set:
            if getattr(self, field) is None and field not in {
                "outline_node_id",
                "chapter_number",
                "story_order",
                "content",
                "markdown",
            }:
                raise ValueError(f"{field} cannot be null.")
        content_fields = {"content_format", "content", "markdown"} & self.model_fields_set
        if content_fields:
            if self.content_format is None:
                raise ValueError("content_format is required when chapter content is updated.")
            if self.content_format == ContentFormat.TIPTAP:
                if self.content is None:
                    raise ValueError("content is required for tiptap format.")
                if self.markdown is not None:
                    raise ValueError("markdown must be omitted for tiptap format.")
            elif self.markdown is None:
                raise ValueError("markdown is required for markdown format.")
            elif self.content is not None:
                raise ValueError("content must be omitted for markdown format.")
        return self


class ChapterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    novel_id: UUID
    outline_node_id: UUID | None
    title: str
    chapter_number: int | None
    story_order: Decimal | None
    status: ChapterStatus
    current_version: int
    summary: str
    created_at: datetime
    updated_at: datetime


class ChapterVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    novel_id: UUID
    chapter_id: UUID
    version_number: int
    content_format: ContentFormat
    tiptap_json: dict[str, object] | None
    markdown: str | None
    plain_text: str
    word_count: int
    created_by: UUID | None
    created_at: datetime


class ChapterPage(BaseModel):
    items: list[ChapterRead]
    next_cursor: str | None
