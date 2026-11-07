from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novelforge.projects.models import NovelStatus


class NovelCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    language: str = Field(default="zh-CN", min_length=2, max_length=32)
    genre: list[str] = Field(default_factory=list, max_length=30)
    premise: str = Field(default="", max_length=20_000)
    writing_preferences: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def strip_title(self) -> "NovelCreate":
        cleaned = self.title.strip()
        if not cleaned:
            raise ValueError("Title cannot be blank.")
        self.title = cleaned
        return self


class NovelUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    language: str | None = Field(default=None, min_length=2, max_length=32)
    genre: list[str] | None = Field(default=None, max_length=30)
    premise: str | None = Field(default=None, max_length=20_000)
    writing_preferences: dict[str, object] | None = None
    status: NovelStatus | None = None

    @model_validator(mode="after")
    def reject_null_updates(self) -> "NovelUpdate":
        for field in self.model_fields_set:
            value = getattr(self, field)
            if value is None:
                raise ValueError(f"{field} cannot be null.")
            if field == "title":
                cleaned = value.strip()
                if not cleaned:
                    raise ValueError("Title cannot be blank.")
                self.title = cleaned
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")
        return self


class NovelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    language: str
    genre: list[str]
    premise: str
    writing_preferences: dict[str, object]
    status: NovelStatus
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
