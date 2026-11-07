from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from novelforge.canon.models import ProposalStatus
from novelforge.canon.revision_schemas import (
    CanonProposalCreate,
    CanonProposalRead,
    CanonRestoreRequest,
    CanonRevisionRead,
    ProposalDecision,
)
from novelforge.canon.revision_service import (
    approve_proposal,
    create_proposal,
    list_proposals,
    list_revisions,
    reject_proposal,
    restore_revision,
)
from novelforge.database import get_db
from novelforge.identity.dependencies import get_current_user, require_csrf
from novelforge.identity.models import User
from novelforge.projects.service import get_novel

router = APIRouter(prefix="/novels/{novel_id}/canon", tags=["canon-approval"])


@router.get("/proposals", response_model=list[CanonProposalRead])
def get_proposals(
    novel_id: UUID,
    proposal_status: ProposalStatus | None = Query(default=None, alias="status"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list:
    get_novel(db, user, novel_id)
    return list_proposals(db, novel_id, proposal_status)


@router.post("/proposals", response_model=CanonProposalRead, status_code=status.HTTP_201_CREATED)
def post_proposal(
    novel_id: UUID,
    payload: CanonProposalCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> object:
    get_novel(db, user, novel_id)
    return create_proposal(
        db,
        novel_id,
        user,
        payload.entity_type,
        payload.entity_id,
        payload.proposed_data,
        payload.rationale,
    )


@router.post("/proposals/{proposal_id}/approve", response_model=CanonProposalRead)
def post_approve_proposal(
    novel_id: UUID,
    proposal_id: UUID,
    payload: ProposalDecision,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> object:
    get_novel(db, user, novel_id)
    return approve_proposal(db, novel_id, proposal_id, user, payload.reason)


@router.post("/proposals/{proposal_id}/reject", response_model=CanonProposalRead)
def post_reject_proposal(
    novel_id: UUID,
    proposal_id: UUID,
    _payload: ProposalDecision | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> object:
    get_novel(db, user, novel_id)
    return reject_proposal(db, novel_id, proposal_id, user)


@router.get("/revisions", response_model=list[CanonRevisionRead])
def get_revisions(
    novel_id: UUID,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list:
    get_novel(db, user, novel_id)
    return list_revisions(db, novel_id, entity_type, entity_id)


@router.post("/revisions/restore", response_model=CanonRevisionRead)
def post_restore_revision(
    novel_id: UUID,
    payload: CanonRestoreRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> object:
    get_novel(db, user, novel_id)
    return restore_revision(db, novel_id, payload.revision_id, user, payload.reason)
