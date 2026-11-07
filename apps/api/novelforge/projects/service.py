from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from novelforge.database import utc_now
from novelforge.errors import Problem
from novelforge.identity.models import User
from novelforge.projects.models import Novel, NovelStatus
from novelforge.projects.schemas import NovelCreate, NovelUpdate


def create_novel(db: Session, owner: User, payload: NovelCreate) -> Novel:
    novel = Novel(owner=owner, **payload.model_dump())
    db.add(novel)
    db.commit()
    db.refresh(novel)
    return novel


def list_novels(db: Session, owner: User, include_archived: bool) -> list[Novel]:
    statement = select(Novel).where(Novel.owner_user_id == owner.id)
    if not include_archived:
        statement = statement.where(Novel.status == NovelStatus.ACTIVE)
    return list(db.scalars(statement.order_by(Novel.created_at.desc(), Novel.id)).all())


def get_novel(db: Session, owner: User, novel_id: UUID) -> Novel:
    novel = db.scalar(select(Novel).where(Novel.id == novel_id, Novel.owner_user_id == owner.id))
    if novel is None:
        raise Problem(
            404, "NOVEL_NOT_FOUND", "Novel not found", "The requested novel was not found."
        )
    return novel


def update_novel(db: Session, novel: Novel, payload: NovelUpdate) -> Novel:
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "status":
            novel.status = value
            novel.archived_at = utc_now() if value == NovelStatus.ARCHIVED else None
        else:
            setattr(novel, field, value)
    db.commit()
    db.refresh(novel)
    return novel


def archive_novel(db: Session, novel: Novel) -> None:
    novel.status = NovelStatus.ARCHIVED
    novel.archived_at = utc_now()
    db.commit()
