import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from novelforge.canon.models import Character, CharacterState, StoryEvent
from novelforge.consistency.models import ConsistencyIssue, IssueStatus
from novelforge.errors import Problem
from novelforge.identity.models import User
from novelforge.planning.models import Chapter
from novelforge.projects.service import get_novel


def _fingerprint(issue_type: str, evidence: dict) -> str:
    return hashlib.sha256(json.dumps([issue_type, evidence], sort_keys=True).encode()).hexdigest()


def run_checks(db: Session, owner: User, novel_id: UUID) -> list[ConsistencyIssue]:
    get_novel(db, owner, novel_id)
    findings: list[tuple[str, str, str, dict]] = []
    states = list(
        db.scalars(select(CharacterState).where(CharacterState.novel_id == novel_id)).all()
    )
    for state in states:
        character_exists = db.scalar(
            select(Character.id).where(
                Character.novel_id == novel_id, Character.id == state.character_id
            )
        )
        if character_exists is None:
            findings.append(
                (
                    "unknown_character",
                    "error",
                    "Character state references an unknown character.",
                    {"state_id": str(state.id), "character_id": str(state.character_id)},
                )
            )
    events = list(
        db.scalars(
            select(StoryEvent)
            .where(StoryEvent.novel_id == novel_id)
            .order_by(StoryEvent.story_order, StoryEvent.id)
        ).all()
    )
    chapters = list(
        db.scalars(
            select(Chapter)
            .where(Chapter.novel_id == novel_id)
            .order_by(Chapter.story_order, Chapter.id)
        ).all()
    )
    for event in events:
        if (
            event.source_chapter_id
            and db.scalar(
                select(Chapter.id).where(
                    Chapter.novel_id == novel_id, Chapter.id == event.source_chapter_id
                )
            )
            is None
        ):
            findings.append(
                (
                    "unknown_chapter",
                    "error",
                    "Story event references an unknown chapter.",
                    {"event_id": str(event.id), "chapter_id": str(event.source_chapter_id)},
                )
            )
    for left, right in zip(events, events[1:], strict=False):
        if left.story_order > right.story_order:
            findings.append(
                (
                    "event_order",
                    "warning",
                    "Story event ordering is inconsistent.",
                    {"left_event_id": str(left.id), "right_event_id": str(right.id)},
                )
            )
    for chapter in chapters:
        if (
            chapter.story_order is not None
            and events
            and chapter.story_order < events[0].story_order
        ):
            findings.append(
                (
                    "chapter_event_order",
                    "warning",
                    "Chapter story order precedes the first event.",
                    {
                        "chapter_id": str(chapter.id),
                        "story_order": str(chapter.story_order),
                        "event_id": str(events[0].id),
                    },
                )
            )
    results = []
    for issue_type, severity, message, evidence in findings:
        fingerprint = _fingerprint(issue_type, evidence)
        issue = db.scalar(
            select(ConsistencyIssue).where(
                ConsistencyIssue.novel_id == novel_id, ConsistencyIssue.fingerprint == fingerprint
            )
        )
        if issue is None:
            issue = ConsistencyIssue(
                novel_id=novel_id,
                issue_type=issue_type,
                severity=severity,
                message=message,
                evidence=evidence,
                fingerprint=fingerprint,
            )
            db.add(issue)
        elif issue.status != IssueStatus.OPEN:
            issue.status = IssueStatus.OPEN
            issue.resolved_by = None
            issue.resolved_at = None
        results.append(issue)
    db.flush()
    db.commit()
    return results


def list_issues(
    db: Session, owner: User, novel_id: UUID, status: IssueStatus | None
) -> list[ConsistencyIssue]:
    get_novel(db, owner, novel_id)
    statement = select(ConsistencyIssue).where(ConsistencyIssue.novel_id == novel_id)
    if status is not None:
        statement = statement.where(ConsistencyIssue.status == status)
    return list(db.scalars(statement.order_by(ConsistencyIssue.created_at.desc())).all())


def resolve_issue(
    db: Session, owner: User, novel_id: UUID, issue_id: UUID, status: IssueStatus
) -> ConsistencyIssue:
    get_novel(db, owner, novel_id)
    issue = db.scalar(
        select(ConsistencyIssue).where(
            ConsistencyIssue.novel_id == novel_id, ConsistencyIssue.id == issue_id
        )
    )
    if issue is None:
        raise Problem(
            404,
            "CONSISTENCY_ISSUE_NOT_FOUND",
            "Consistency issue not found",
            "The issue is not in this novel.",
        )
    if status == IssueStatus.OPEN:
        raise Problem(
            422,
            "INVALID_ISSUE_STATUS",
            "Invalid issue status",
            "Resolution must use a non-open status.",
        )
    issue.status = status
    issue.resolved_by = owner.id
    issue.resolved_at = datetime.now(UTC)
    issue.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(issue)
    return issue
