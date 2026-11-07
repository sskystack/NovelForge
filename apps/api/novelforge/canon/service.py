from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from novelforge.canon.models import CanonStatus, Character, Faction, Location, WorldRule
from novelforge.database import utc_now
from novelforge.errors import Problem
from novelforge.identity.models import User
from novelforge.projects.service import get_novel

CanonModel = type[Character] | type[Location] | type[Faction] | type[WorldRule]


def list_entities(
    db: Session,
    owner: User,
    novel_id: UUID,
    model: CanonModel,
    include_non_canon: bool,
) -> list[Any]:
    get_novel(db, owner, novel_id)
    statement = select(model).where(model.novel_id == novel_id)
    if not include_non_canon:
        statement = statement.where(model.canon_status == CanonStatus.CANON)
    return list(db.scalars(statement.order_by(model.created_at, model.id)).all())


def create_entity(
    db: Session,
    owner: User,
    novel_id: UUID,
    model: CanonModel,
    values: dict[str, Any],
) -> Any:
    novel = get_novel(db, owner, novel_id)
    entity = model(novel_id=novel.id, **values)
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


def get_entity(db: Session, novel_id: UUID, entity_id: UUID, model: CanonModel) -> Any:
    entity = db.scalar(select(model).where(model.id == entity_id, model.novel_id == novel_id))
    if entity is None:
        raise Problem(
            404,
            "CANON_ENTITY_NOT_FOUND",
            "Canon record not found",
            "The requested canon record was not found.",
        )
    return entity


def ensure_novel_access(db: Session, owner: User, novel_id: UUID) -> None:
    get_novel(db, owner, novel_id)


def update_entity(
    db: Session,
    entity: Any,
    values: dict[str, Any],
) -> Any:
    if entity.canon_status == CanonStatus.CANON:
        raise Problem(
            403,
            "CANON_REVISION_REQUIRED",
            "Canon revision required",
            "Approved canon records can only change through a revision workflow.",
        )
    for field, value in values.items():
        if field == "canon_status" and value == CanonStatus.CANON:
            raise Problem(
                403,
                "CANON_APPROVAL_REQUIRED",
                "Approval required",
                "Canon records can only be approved through the approval workflow.",
            )
        setattr(entity, field, value)
    entity.updated_at = utc_now()
    db.commit()
    db.refresh(entity)
    return entity


def delete_entity(db: Session, entity: Any) -> None:
    if entity.canon_status == CanonStatus.CANON:
        raise Problem(
            403,
            "CANON_REVISION_REQUIRED",
            "Canon revision required",
            "Approved canon records cannot be deleted directly.",
        )
    db.delete(entity)
    db.commit()
