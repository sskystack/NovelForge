from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChapterAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    novel_id: UUID
    chapter_id: UUID
    chapter_version_id: UUID
    status: str
    summary_candidate: str
    candidates: dict
    proposal_ids: list
    warnings: list
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class ProposalSummaryRead(BaseModel):
    id: UUID
    entity_type: str
    entity_id: UUID | None
    proposed_data: dict
    rationale: str
    status: str
    created_at: datetime


class ProposalAction(BaseModel):
    reason: str = Field(default="", max_length=20_000)
