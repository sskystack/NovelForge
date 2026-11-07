from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from novelforge.canon.models import (
    CanonStatus,
    Character,
    CharacterState,
    Relationship,
    StoryEvent,
)
from novelforge.canon.state_schemas import (
    CharacterStateCreate,
    RelationshipCreate,
    StoryEventCreate,
)
from novelforge.errors import Problem


def _not_found(code: str, title: str, detail: str) -> Problem:
    return Problem(404, code, title, detail)


def create_story_event(
    db: Session,
    novel_id: UUID,
    payload: StoryEventCreate,
) -> StoryEvent:
    event = StoryEvent(novel_id=novel_id, **payload.model_dump())
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def list_story_events(db: Session, novel_id: UUID) -> list[StoryEvent]:
    statement = select(StoryEvent).where(StoryEvent.novel_id == novel_id)
    return list(db.scalars(statement.order_by(StoryEvent.story_order, StoryEvent.id)).all())


def create_character_state(
    db: Session,
    novel_id: UUID,
    character_id: UUID,
    payload: CharacterStateCreate,
) -> CharacterState:
    if (
        db.scalar(
            select(Character.id).where(Character.id == character_id, Character.novel_id == novel_id)
        )
        is None
    ):
        raise _not_found(
            "CANON_ENTITY_NOT_FOUND",
            "Character not found",
            "The character was not found in this novel.",
        )
    if (
        payload.source_event_id is not None
        and db.scalar(
            select(StoryEvent.id).where(
                StoryEvent.id == payload.source_event_id,
                StoryEvent.novel_id == novel_id,
            )
        )
        is None
    ):
        raise _not_found(
            "STORY_EVENT_NOT_FOUND",
            "Story event not found",
            "The event was not found in this novel.",
        )
    state = CharacterState(
        novel_id=novel_id,
        character_id=character_id,
        **payload.model_dump(),
    )
    db.add(state)
    db.commit()
    db.refresh(state)
    return state


def list_character_states(
    db: Session,
    novel_id: UUID,
    character_id: UUID,
) -> list[CharacterState]:
    character_exists = db.scalar(
        select(Character.id).where(Character.id == character_id, Character.novel_id == novel_id)
    )
    if character_exists is None:
        raise _not_found(
            "CANON_ENTITY_NOT_FOUND",
            "Character not found",
            "The character was not found in this novel.",
        )
    statement = select(CharacterState).where(
        CharacterState.novel_id == novel_id,
        CharacterState.character_id == character_id,
    )
    return list(db.scalars(statement.order_by(CharacterState.story_order, CharacterState.id)).all())


def get_character_state_at(
    db: Session,
    novel_id: UUID,
    character_id: UUID,
    story_order: Decimal,
) -> CharacterState | None:
    if (
        db.scalar(
            select(Character.id).where(Character.id == character_id, Character.novel_id == novel_id)
        )
        is None
    ):
        raise _not_found(
            "CANON_ENTITY_NOT_FOUND",
            "Character not found",
            "The character was not found in this novel.",
        )
    statement = (
        select(CharacterState)
        .where(
            CharacterState.novel_id == novel_id,
            CharacterState.character_id == character_id,
            CharacterState.story_order <= story_order,
            or_(
                CharacterState.valid_to_order.is_(None), story_order < CharacterState.valid_to_order
            ),
            CharacterState.canon_status == CanonStatus.CANON,
        )
        .order_by(CharacterState.story_order.desc(), CharacterState.id)
        .limit(1)
    )
    return db.scalar(statement)


def list_character_states_at(
    db: Session,
    novel_id: UUID,
    story_order: Decimal,
) -> list[CharacterState]:
    statement = (
        select(CharacterState)
        .where(
            CharacterState.novel_id == novel_id,
            CharacterState.story_order <= story_order,
            or_(
                CharacterState.valid_to_order.is_(None), story_order < CharacterState.valid_to_order
            ),
            CharacterState.canon_status == CanonStatus.CANON,
        )
        .order_by(CharacterState.character_id, CharacterState.story_order.desc())
    )
    selected: dict[UUID, CharacterState] = {}
    for state in db.scalars(statement).all():
        selected.setdefault(state.character_id, state)
    return list(selected.values())


def create_relationship(
    db: Session,
    novel_id: UUID,
    payload: RelationshipCreate,
) -> Relationship:
    endpoint_ids = {payload.from_character_id, payload.to_character_id}
    found_ids = set(
        db.scalars(
            select(Character.id).where(
                Character.novel_id == novel_id, Character.id.in_(endpoint_ids)
            )
        ).all()
    )
    if found_ids != endpoint_ids:
        raise _not_found(
            "RELATIONSHIP_ENDPOINT_NOT_FOUND",
            "Character not found",
            "Both relationship endpoints must belong to this novel.",
        )
    relationship = Relationship(novel_id=novel_id, **payload.model_dump())
    db.add(relationship)
    db.commit()
    db.refresh(relationship)
    return relationship


def list_relationships(
    db: Session,
    novel_id: UUID,
    story_order: Decimal | None = None,
    include_non_canon: bool = False,
) -> list[Relationship]:
    statement = select(Relationship).where(Relationship.novel_id == novel_id)
    if not include_non_canon:
        statement = statement.where(Relationship.canon_status == CanonStatus.CANON)
    if story_order is not None:
        statement = statement.where(
            and_(
                or_(
                    Relationship.valid_from_order.is_(None),
                    Relationship.valid_from_order <= story_order,
                ),
                or_(
                    Relationship.valid_to_order.is_(None), story_order < Relationship.valid_to_order
                ),
            )
        )
    return list(
        db.scalars(
            statement.order_by(Relationship.from_character_id, Relationship.to_character_id)
        ).all()
    )
