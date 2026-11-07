from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novelforge.canon.models import CanonStatus


class StoryEventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=50_000)
    story_order: Decimal = Field(ge=0, max_digits=20, decimal_places=6)
    story_time_label: str | None = Field(default=None, max_length=120)
    occurred_at: datetime | None = None
    event_type: str = Field(default="general", min_length=1, max_length=80)
    canon_status: CanonStatus = CanonStatus.DRAFT

    @model_validator(mode="after")
    def strip_title(self):
        if self.canon_status == CanonStatus.CANON:
            raise ValueError("Story events require the approval workflow to become canon.")
        self.title = self.title.strip()
        if not self.title:
            raise ValueError("Event title cannot be blank.")
        return self


class StoryEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    novel_id: UUID
    title: str
    description: str
    story_order: Decimal
    story_time_label: str | None
    event_type: str
    source_chapter_id: UUID | None
    canon_status: CanonStatus
    occurred_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CharacterStateCreate(BaseModel):
    story_order: Decimal = Field(ge=0, max_digits=20, decimal_places=6)
    valid_to_order: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=6)
    state: dict[str, object]
    source_event_id: UUID | None = None
    canon_status: CanonStatus = CanonStatus.PROPOSED

    @model_validator(mode="after")
    def validate_interval(self):
        if self.valid_to_order is not None and self.valid_to_order <= self.story_order:
            raise ValueError("valid_to_order must be greater than story_order.")
        if self.canon_status == CanonStatus.CANON:
            raise ValueError("Character state requires the approval workflow to become canon.")
        return self


class CharacterStateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    novel_id: UUID
    character_id: UUID
    story_order: Decimal
    valid_to_order: Decimal | None
    state: dict[str, object]
    source_event_id: UUID | None
    canon_status: CanonStatus
    created_at: datetime


class CharacterStateAtRead(BaseModel):
    character_id: UUID
    story_order: Decimal
    state: CharacterStateRead | None


class RelationshipCreate(BaseModel):
    from_character_id: UUID
    to_character_id: UUID
    relationship_type: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=50_000)
    valid_from_order: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=6)
    valid_to_order: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=6)
    canon_status: CanonStatus = CanonStatus.DRAFT
    attributes: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_relationship(self):
        self.relationship_type = self.relationship_type.strip()
        if not self.relationship_type:
            raise ValueError("relationship_type cannot be blank.")
        if self.from_character_id == self.to_character_id:
            raise ValueError("A character cannot have a relationship with itself.")
        if (
            self.valid_from_order is not None
            and self.valid_to_order is not None
            and self.valid_to_order <= self.valid_from_order
        ):
            raise ValueError("valid_to_order must be greater than valid_from_order.")
        if self.canon_status == CanonStatus.CANON:
            raise ValueError("Relationships require the approval workflow to become canon.")
        return self


class RelationshipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    novel_id: UUID
    from_character_id: UUID
    to_character_id: UUID
    relationship_type: str
    description: str
    valid_from_order: Decimal | None
    valid_to_order: Decimal | None
    canon_status: CanonStatus
    attributes: dict[str, object]
    created_at: datetime
    updated_at: datetime
