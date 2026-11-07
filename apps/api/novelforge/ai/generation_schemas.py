from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from novelforge.ai.generation_models import GenerationStatus, TaskProfile


class GenerationCreate(BaseModel):
    chapter_id: UUID | None = None
    task_profile: TaskProfile = TaskProfile.WRITING
    instructions: str = Field(default="", max_length=20_000)
    model: str = Field(default="mock-chat", max_length=200)
    token_budget: int = Field(default=4000, ge=100, le=20_000)


class GenerationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    novel_id: UUID
    chapter_id: UUID | None
    task_profile: TaskProfile
    status: GenerationStatus
    instructions: str
    model: str
    provider: str
    context_snapshot: dict
    output: dict
    error_message: str | None
    expected_version: int | None
    created_at: datetime
    updated_at: datetime


class GenerationAccept(BaseModel):
    expected_version: int = Field(ge=0)
