from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from novelforge.consistency.models import IssueStatus
from novelforge.consistency.service import list_issues, resolve_issue, run_checks
from novelforge.database import get_db
from novelforge.identity.dependencies import get_current_user, require_csrf
from novelforge.identity.models import User

router = APIRouter(prefix="/novels/{novel_id}/consistency", tags=["consistency"])


class IssueResolution(BaseModel):
    status: IssueStatus


@router.post("/check")
def check_consistency(
    novel_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    return run_checks(db, user, novel_id)


@router.get("/issues")
def get_consistency_issues(
    novel_id: UUID,
    status: IssueStatus | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_issues(db, user, novel_id, status)


@router.post("/issues/{issue_id}/resolve")
def post_resolve_issue(
    novel_id: UUID,
    issue_id: UUID,
    payload: IssueResolution,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    return resolve_issue(db, user, novel_id, issue_id, payload.status)
