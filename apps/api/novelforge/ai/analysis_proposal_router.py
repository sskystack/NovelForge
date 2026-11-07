from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from novelforge.ai.analysis_proposal_models import AnalysisProposal, AnalysisProposalStatus
from novelforge.ai.analysis_schemas import ProposalAction
from novelforge.ai.factory import create_chat_provider
from novelforge.canon.models import StoryEvent
from novelforge.canon.revision_service import approve_proposal, create_proposal
from novelforge.database import get_db
from novelforge.errors import Problem
from novelforge.identity.dependencies import get_current_user, get_settings, require_csrf
from novelforge.identity.models import User
from novelforge.knowledge.models import KnowledgeVisibility
from novelforge.knowledge.service import SourceMaterial, ingest_source
from novelforge.projects.service import get_novel
from novelforge.settings import Settings

router = APIRouter(
    prefix="/novels/{novel_id}/ai/analysis-proposals", tags=["ai-analysis-proposals"]
)


@router.get("")
def list_analysis_proposals(
    novel_id: UUID,
    status: AnalysisProposalStatus | None = Query(default=None),
    chapter_version_id: UUID | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_novel(db, user, novel_id)
    statement = select(AnalysisProposal).where(AnalysisProposal.novel_id == novel_id)
    if status is not None:
        statement = statement.where(AnalysisProposal.status == status)
    if chapter_version_id is not None:
        statement = statement.where(AnalysisProposal.chapter_version_id == chapter_version_id)
    return list(db.scalars(statement.order_by(AnalysisProposal.created_at.desc())).all())


def _get(db: Session, user: User, novel_id: UUID, proposal_id: UUID) -> AnalysisProposal:
    get_novel(db, user, novel_id)
    proposal = db.scalar(
        select(AnalysisProposal).where(
            AnalysisProposal.novel_id == novel_id, AnalysisProposal.id == proposal_id
        )
    )
    if proposal is None:
        raise Problem(
            404,
            "ANALYSIS_PROPOSAL_NOT_FOUND",
            "Analysis proposal not found",
            "The proposal is not in this novel.",
        )
    return proposal


@router.post("/{proposal_id}/approve")
def approve_analysis_proposal(
    novel_id: UUID,
    proposal_id: UUID,
    payload: ProposalAction,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
):
    proposal = _get(db, user, novel_id, proposal_id)
    if proposal.status != AnalysisProposalStatus.PENDING:
        raise Problem(
            409,
            "ANALYSIS_PROPOSAL_ALREADY_REVIEWED",
            "Proposal already reviewed",
            "Only pending proposals can be approved.",
        )
    entity_type = "story_event" if proposal.proposal_type == "event" else "character_state"
    proposed_data = {key: value for key, value in proposal.payload.items() if key != "evidence"}
    canon_proposal = create_proposal(
        db,
        novel_id,
        user,
        entity_type,
        None,
        proposed_data,
        payload.reason
        or f"Approved analysis from chapter version {proposal.evidence.get('version_number', '?')}",
    )
    accepted_canon = approve_proposal(db, novel_id, canon_proposal.id, user, payload.reason)
    if proposal.proposal_type == "event":
        event = db.scalar(
            select(StoryEvent).where(
                StoryEvent.novel_id == novel_id, StoryEvent.id == accepted_canon.entity_id
            )
        )
        provider = create_chat_provider(settings)
        if event is not None and hasattr(provider, "embed"):
            try:
                ingest_source(
                    db,
                    novel_id,
                    SourceMaterial(
                        source_type="story_event",
                        source_id=event.id,
                        title=event.title,
                        source_revision=1,
                        content=f"{event.title}\n{event.description}",
                        visibility=KnowledgeVisibility.APPROVED,
                    ),
                    provider,
                )
            except Problem:
                pass
    proposal.status = AnalysisProposalStatus.APPROVED
    proposal.reviewed_by = user.id
    proposal.reviewed_at = datetime.now(UTC)
    db.commit()
    db.refresh(proposal)
    return proposal


@router.post("/{proposal_id}/reject")
def reject_analysis_proposal(
    novel_id: UUID,
    proposal_id: UUID,
    payload: ProposalAction,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    proposal = _get(db, user, novel_id, proposal_id)
    if proposal.status != AnalysisProposalStatus.PENDING:
        raise Problem(
            409,
            "ANALYSIS_PROPOSAL_ALREADY_REVIEWED",
            "Proposal already reviewed",
            "Only pending proposals can be rejected.",
        )
    proposal.status = AnalysisProposalStatus.REJECTED
    proposal.reviewed_by = user.id
    proposal.reviewed_at = datetime.now(UTC)
    db.commit()
    db.refresh(proposal)
    return proposal
