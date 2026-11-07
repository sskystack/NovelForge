from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from novelforge.canon.models import CanonStatus

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
RequiredDescription = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50_000)
]
Category = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class CanonCreateBase(BaseModel):
    canon_status: CanonStatus = CanonStatus.DRAFT

    @model_validator(mode="after")
    def validate_initial_status(self):
        if self.canon_status == CanonStatus.CANON:
            raise ValueError("New canon records must be approved in a later workflow.")
        return self


class CanonUpdateBase(BaseModel):
    canon_status: CanonStatus | None = None

    @model_validator(mode="after")
    def validate_status_transition(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null.")
        if self.canon_status == CanonStatus.CANON:
            raise ValueError("Canon status requires the approval workflow.")
        return self


class CharacterCreate(CanonCreateBase):
    name: ShortText
    aliases: list[str] = Field(default_factory=list, max_length=100)
    summary: str = Field(default="", max_length=20_000)
    personality: dict[str, object] = Field(default_factory=dict)
    background: str = Field(default="", max_length=50_000)
    goals: list[str] = Field(default_factory=list, max_length=100)
    constraints: list[str] = Field(default_factory=list, max_length=100)
    attributes: dict[str, object] = Field(default_factory=dict)


class CharacterUpdate(CanonUpdateBase):
    name: ShortText | None = None
    aliases: list[str] | None = Field(default=None, max_length=100)
    summary: str | None = Field(default=None, max_length=20_000)
    personality: dict[str, object] | None = None
    background: str | None = Field(default=None, max_length=50_000)
    goals: list[str] | None = Field(default=None, max_length=100)
    constraints: list[str] | None = Field(default=None, max_length=100)
    attributes: dict[str, object] | None = None


class LocationCreate(CanonCreateBase):
    name: ShortText
    description: str = Field(default="", max_length=50_000)
    attributes: dict[str, object] = Field(default_factory=dict)


class LocationUpdate(CanonUpdateBase):
    name: ShortText | None = None
    description: str | None = Field(default=None, max_length=50_000)
    attributes: dict[str, object] | None = None


class FactionCreate(CanonCreateBase):
    name: ShortText
    description: str = Field(default="", max_length=50_000)
    attributes: dict[str, object] = Field(default_factory=dict)


class FactionUpdate(CanonUpdateBase):
    name: ShortText | None = None
    description: str | None = Field(default=None, max_length=50_000)
    attributes: dict[str, object] | None = None


class WorldRuleCreate(CanonCreateBase):
    title: ShortText
    category: Category = "general"
    description: RequiredDescription
    constraints: dict[str, object] = Field(default_factory=dict)


class WorldRuleUpdate(CanonUpdateBase):
    title: ShortText | None = None
    category: Category | None = None
    description: RequiredDescription | None = None
    constraints: dict[str, object] | None = None


class CanonReadBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    novel_id: UUID
    canon_status: CanonStatus
    created_at: datetime
    updated_at: datetime


class CharacterRead(CanonReadBase):
    name: str
    aliases: list[str]
    summary: str
    personality: dict[str, object]
    background: str
    goals: list[str]
    constraints: list[str]
    attributes: dict[str, object]


class LocationRead(CanonReadBase):
    name: str
    description: str
    attributes: dict[str, object]


class FactionRead(CanonReadBase):
    name: str
    description: str
    attributes: dict[str, object]


class WorldRuleRead(CanonReadBase):
    title: str
    category: str
    description: str
    constraints: dict[str, object]
