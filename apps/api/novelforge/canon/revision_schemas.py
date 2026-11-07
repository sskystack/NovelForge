from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

EntityType = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]


class CanonProposalCreate(BaseModel):
    entity_type: EntityType
    entity_id: UUID | None = None
    proposed_data: dict[str, object]
    rationale: str = Field(default="", max_length=20_000)


class ProposalDecision(BaseModel):
    reason: str = Field(default="", max_length=20_000)


class CanonProposalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    novel_id: UUID
    entity_type: str
    entity_id: UUID | None
    proposed_data: dict[str, object]
    rationale: str
    created_by: UUID | None
    status: str
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    created_at: datetime


class CanonRevisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    novel_id: UUID
    entity_type: str
    entity_id: UUID
    revision_number: int
    before_data: dict[str, object] | None
    after_data: dict[str, object]
    change_reason: str
    actor_user_id: UUID | None
    source_proposal_id: UUID | None
    created_at: datetime


class CanonRestoreRequest(BaseModel):
    revision_id: UUID
    reason: str = Field(default="Restored from revision history", max_length=20_000)
