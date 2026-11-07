from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from novelforge.canon.models import (
    CanonProposal,
    CanonRevision,
    CanonStatus,
    Character,
    CharacterState,
    Faction,
    Location,
    ProposalStatus,
    Relationship,
    StoryEvent,
    WorldRule,
)
from novelforge.canon.schemas import (
    CharacterCreate,
    CharacterUpdate,
    FactionCreate,
    FactionUpdate,
    LocationCreate,
    LocationUpdate,
    WorldRuleCreate,
    WorldRuleUpdate,
)
from novelforge.canon.state_schemas import (
    CharacterStateCreate,
    RelationshipCreate,
    StoryEventCreate,
)
from novelforge.errors import Problem
from novelforge.identity.models import User

ENTITY_MODELS: dict[str, type] = {
    "character": Character,
    "location": Location,
    "faction": Faction,
    "world_rule": WorldRule,
    "story_event": StoryEvent,
    "character_state": CharacterState,
    "relationship": Relationship,
}

CREATE_SCHEMAS: dict[str, type[BaseModel]] = {
    "character": CharacterCreate,
    "location": LocationCreate,
    "faction": FactionCreate,
    "world_rule": WorldRuleCreate,
    "story_event": StoryEventCreate,
    "character_state": CharacterStateCreate,
    "relationship": RelationshipCreate,
}

UPDATE_SCHEMAS: dict[str, type[BaseModel]] = {
    "character": CharacterUpdate,
    "location": LocationUpdate,
    "faction": FactionUpdate,
    "world_rule": WorldRuleUpdate,
}


def _problem(status: int, code: str, title: str, detail: str) -> Problem:
    return Problem(status, code, title, detail)


def _validate_payload(
    entity_type: str, entity_id: UUID | None, data: dict[str, Any]
) -> dict[str, Any]:
    if entity_type not in ENTITY_MODELS:
        raise _problem(
            422,
            "UNKNOWN_CANON_ENTITY_TYPE",
            "Unsupported entity type",
            "This entity type cannot become canon.",
        )
    if entity_type == "character_state" and entity_id is None:
        character_id = data.get("character_id")
        if not isinstance(character_id, str | UUID):
            raise _problem(
                422,
                "CHARACTER_REQUIRED",
                "Character required",
                "A character state needs character_id.",
            )
        try:
            data = {**data, "character_id": str(UUID(str(character_id)))}
        except ValueError as error:
            raise _problem(
                422,
                "INVALID_CANON_PROPOSAL",
                "Invalid canon proposal",
                "character_id must be a UUID.",
            ) from error
        state_values = {key: value for key, value in data.items() if key != "character_id"}
        schema = CREATE_SCHEMAS[entity_type]
        try:
            parsed = schema.model_validate(state_values)
        except ValidationError as error:
            raise _problem(
                422, "INVALID_CANON_PROPOSAL", "Invalid canon proposal", str(error)
            ) from error
        values = parsed.model_dump(mode="json")
        if values.get("canon_status") == CanonStatus.CANON:
            raise _problem(
                422,
                "INVALID_CANON_PROPOSAL",
                "Invalid canon proposal",
                "Proposal payload cannot set canon status.",
            )
        values.pop("canon_status", None)
        return {**values, "character_id": data["character_id"]}
    schema = (
        CREATE_SCHEMAS.get(entity_type) if entity_id is None else UPDATE_SCHEMAS.get(entity_type)
    )
    if schema is None:
        raise _problem(
            422,
            "ENTITY_UPDATE_NOT_SUPPORTED",
            "Unsupported update",
            "This entity type can only be proposed as a new record.",
        )
    try:
        parsed = schema.model_validate(data)
    except ValidationError as error:
        raise _problem(
            422, "INVALID_CANON_PROPOSAL", "Invalid canon proposal", str(error)
        ) from error
    values = parsed.model_dump(mode="json", exclude_unset=entity_id is not None)
    if not values:
        raise _problem(
            422,
            "INVALID_CANON_PROPOSAL",
            "Invalid canon proposal",
            "Proposal data must include at least one field.",
        )
    if "canon_status" in values:
        if values["canon_status"] == CanonStatus.CANON:
            raise _problem(
                422,
                "INVALID_CANON_PROPOSAL",
                "Invalid canon proposal",
                "Proposal payload cannot set canon status.",
            )
        values.pop("canon_status")
    return values


def create_proposal(
    db: Session,
    novel_id: UUID,
    actor: User,
    entity_type: str,
    entity_id: UUID | None,
    proposed_data: dict[str, Any],
    rationale: str,
) -> CanonProposal:
    values = _validate_payload(entity_type, entity_id, proposed_data)
    model = ENTITY_MODELS[entity_type]
    if entity_id is not None:
        entity = db.scalar(select(model).where(model.novel_id == novel_id, model.id == entity_id))
        if entity is None:
            raise _problem(
                404,
                "CANON_ENTITY_NOT_FOUND",
                "Canon record not found",
                "The target record was not found in this novel.",
            )
    proposal = CanonProposal(
        novel_id=novel_id,
        entity_type=entity_type,
        entity_id=entity_id,
        proposed_data=values,
        rationale=rationale.strip(),
        created_by=actor.id,
    )
    db.add(proposal)
    db.commit()
    db.refresh(proposal)
    return proposal


def list_proposals(
    db: Session, novel_id: UUID, status: ProposalStatus | None
) -> list[CanonProposal]:
    statement = select(CanonProposal).where(CanonProposal.novel_id == novel_id)
    if status is not None:
        statement = statement.where(CanonProposal.status == status)
    return list(
        db.scalars(statement.order_by(CanonProposal.created_at.desc(), CanonProposal.id)).all()
    )


def list_revisions(
    db: Session,
    novel_id: UUID,
    entity_type: str | None,
    entity_id: UUID | None,
) -> list[CanonRevision]:
    statement = select(CanonRevision).where(CanonRevision.novel_id == novel_id)
    if entity_type is not None:
        statement = statement.where(CanonRevision.entity_type == entity_type)
    if entity_id is not None:
        statement = statement.where(CanonRevision.entity_id == entity_id)
    return list(
        db.scalars(
            statement.order_by(
                CanonRevision.created_at.desc(), CanonRevision.revision_number.desc()
            )
        ).all()
    )


def _entity_snapshot(entity: Any) -> dict[str, Any]:
    excluded = {"_sa_instance_state", "novel_id", "created_at", "updated_at"}
    return {
        column.key: getattr(entity, column.key)
        for column in entity.__table__.columns
        if column.key not in excluded and column.key != "id"
    }


def _next_revision_number(db: Session, novel_id: UUID, entity_type: str, entity_id: UUID) -> int:
    current = db.scalar(
        select(func.max(CanonRevision.revision_number)).where(
            CanonRevision.novel_id == novel_id,
            CanonRevision.entity_type == entity_type,
            CanonRevision.entity_id == entity_id,
        )
    )
    return int(current or 0) + 1


def _append_revision(
    db: Session,
    *,
    novel_id: UUID,
    entity_type: str,
    entity_id: UUID,
    before: dict[str, Any] | None,
    after: dict[str, Any],
    actor_id: UUID,
    reason: str,
    proposal_id: UUID | None,
) -> CanonRevision:
    revision = CanonRevision(
        novel_id=novel_id,
        entity_type=entity_type,
        entity_id=entity_id,
        revision_number=_next_revision_number(db, novel_id, entity_type, entity_id),
        before_data=before,
        after_data=after,
        change_reason=reason,
        actor_user_id=actor_id,
        source_proposal_id=proposal_id,
    )
    db.add(revision)
    return revision


def _create_canon_entity(
    db: Session,
    novel_id: UUID,
    entity_type: str,
    values: dict[str, Any],
) -> Any:
    if entity_type == "character_state":
        values = dict(values)
        character_id = UUID(str(values.pop("character_id")))
        _require_character(db, novel_id, character_id)
        entity = CharacterState(novel_id=novel_id, character_id=character_id, **values)
        db.add(entity)
        db.flush()
        return entity
    if entity_type == "relationship":
        values = dict(values)
        raw_from_id = values.pop("from_character_id", None)
        raw_to_id = values.pop("to_character_id", None)
        if raw_from_id is None or raw_to_id is None:
            raise _problem(
                422,
                "RELATIONSHIP_ENDPOINT_REQUIRED",
                "Relationship endpoints required",
                "Both character endpoints are required.",
            )
        from_character_id = UUID(str(raw_from_id))
        to_character_id = UUID(str(raw_to_id))
        _require_character(db, novel_id, from_character_id)
        _require_character(db, novel_id, to_character_id)
        if from_character_id == to_character_id:
            raise _problem(
                422,
                "INVALID_RELATIONSHIP",
                "Invalid relationship",
                "A character cannot relate to itself.",
            )
        entity = Relationship(
            novel_id=novel_id,
            from_character_id=from_character_id,
            to_character_id=to_character_id,
            **values,
        )
        db.add(entity)
        db.flush()
        return entity
    model = ENTITY_MODELS[entity_type]
    entity = model(novel_id=novel_id, **values)
    db.add(entity)
    db.flush()
    return entity


def _require_character(db: Session, novel_id: UUID, character_id: UUID) -> None:
    if (
        db.scalar(
            select(Character.id).where(Character.novel_id == novel_id, Character.id == character_id)
        )
        is None
    ):
        raise _problem(
            404,
            "CANON_ENTITY_NOT_FOUND",
            "Character not found",
            "The character was not found in this novel.",
        )


def approve_proposal(
    db: Session,
    novel_id: UUID,
    proposal_id: UUID,
    reviewer: User,
    reason: str,
) -> CanonProposal:
    proposal = db.scalar(
        select(CanonProposal)
        .where(CanonProposal.novel_id == novel_id, CanonProposal.id == proposal_id)
        .with_for_update()
    )
    if proposal is None:
        raise _problem(
            404,
            "CANON_PROPOSAL_NOT_FOUND",
            "Proposal not found",
            "The proposal was not found in this novel.",
        )
    if proposal.status != ProposalStatus.PENDING:
        raise _problem(
            409,
            "CANON_PROPOSAL_ALREADY_REVIEWED",
            "Proposal already reviewed",
            "Only pending proposals can be approved.",
        )
    model = ENTITY_MODELS.get(proposal.entity_type)
    if model is None:
        raise _problem(
            422,
            "UNKNOWN_CANON_ENTITY_TYPE",
            "Unsupported entity type",
            "This entity type cannot become canon.",
        )
    if proposal.entity_id is None:
        entity = _create_canon_entity(
            db, novel_id, proposal.entity_type, dict(proposal.proposed_data)
        )
        entity.canon_status = CanonStatus.CANON
        entity_id = entity.id
        before = None
        after = _entity_snapshot(entity)
    else:
        entity = db.scalar(
            select(model)
            .where(model.novel_id == novel_id, model.id == proposal.entity_id)
            .with_for_update()
        )
        if entity is None:
            raise _problem(
                404,
                "CANON_ENTITY_NOT_FOUND",
                "Canon record not found",
                "The target record was removed before approval.",
            )
        before = _entity_snapshot(entity)
        for field, value in proposal.proposed_data.items():
            setattr(entity, field, value)
        entity.canon_status = CanonStatus.CANON
        if hasattr(entity, "updated_at"):
            entity.updated_at = datetime.now(UTC)
        entity_id = entity.id
        after = _entity_snapshot(entity)
    entity.canon_status = CanonStatus.CANON
    _append_revision(
        db,
        novel_id=novel_id,
        entity_type=proposal.entity_type,
        entity_id=entity_id,
        before=before,
        after=after,
        actor_id=reviewer.id,
        reason=reason.strip() or proposal.rationale,
        proposal_id=proposal.id,
    )
    db.flush()
    proposal.entity_id = entity_id
    proposal.status = ProposalStatus.APPROVED
    proposal.reviewed_by = reviewer.id
    proposal.reviewed_at = datetime.now(UTC)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise _problem(
            409,
            "CANON_REVISION_CONFLICT",
            "Revision conflict",
            "The canon changed while this proposal was being approved.",
        ) from error
    db.refresh(proposal)
    return proposal


def reject_proposal(
    db: Session, novel_id: UUID, proposal_id: UUID, reviewer: User
) -> CanonProposal:
    proposal = db.scalar(
        select(CanonProposal)
        .where(CanonProposal.novel_id == novel_id, CanonProposal.id == proposal_id)
        .with_for_update()
    )
    if proposal is None:
        raise _problem(
            404,
            "CANON_PROPOSAL_NOT_FOUND",
            "Proposal not found",
            "The proposal was not found in this novel.",
        )
    if proposal.status != ProposalStatus.PENDING:
        raise _problem(
            409,
            "CANON_PROPOSAL_ALREADY_REVIEWED",
            "Proposal already reviewed",
            "Only pending proposals can be rejected.",
        )
    proposal.status = ProposalStatus.REJECTED
    proposal.reviewed_by = reviewer.id
    proposal.reviewed_at = datetime.now(UTC)
    db.commit()
    db.refresh(proposal)
    return proposal


def restore_revision(
    db: Session,
    novel_id: UUID,
    revision_id: UUID,
    actor: User,
    reason: str,
) -> CanonRevision:
    source = db.scalar(
        select(CanonRevision).where(
            CanonRevision.novel_id == novel_id,
            CanonRevision.id == revision_id,
        )
    )
    if source is None:
        raise _problem(
            404,
            "CANON_REVISION_NOT_FOUND",
            "Revision not found",
            "The revision was not found in this novel.",
        )
    model = ENTITY_MODELS.get(source.entity_type)
    if model is None:
        raise _problem(
            422,
            "UNKNOWN_CANON_ENTITY_TYPE",
            "Unsupported entity type",
            "This revision type cannot be restored.",
        )
    entity = db.scalar(
        select(model)
        .where(model.novel_id == novel_id, model.id == source.entity_id)
        .with_for_update()
    )
    if entity is None:
        raise _problem(
            404,
            "CANON_ENTITY_NOT_FOUND",
            "Canon record not found",
            "The revised record no longer exists.",
        )
    before = _entity_snapshot(entity)
    for field, value in source.after_data.items():
        if field in before and field not in {"canon_status"}:
            setattr(entity, field, value)
    entity.canon_status = CanonStatus.CANON
    if hasattr(entity, "updated_at"):
        entity.updated_at = datetime.now(UTC)
    after = _entity_snapshot(entity)
    new_revision = _append_revision(
        db,
        novel_id=novel_id,
        entity_type=source.entity_type,
        entity_id=source.entity_id,
        before=before,
        after=after,
        actor_id=actor.id,
        reason=reason.strip() or f"Restored from revision {source.revision_number}",
        proposal_id=None,
    )
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise _problem(
            409,
            "CANON_REVISION_CONFLICT",
            "Revision conflict",
            "The canon changed while this revision was being restored.",
        ) from error
    db.refresh(new_revision)
    return new_revision
