from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from novelforge.canon.models import (
    Character,
    CharacterState,
    Faction,
    Location,
    Relationship,
    StoryEvent,
    WorldRule,
)
from novelforge.canon.schemas import (
    CharacterCreate,
    CharacterRead,
    CharacterUpdate,
    FactionCreate,
    FactionRead,
    FactionUpdate,
    LocationCreate,
    LocationRead,
    LocationUpdate,
    WorldRuleCreate,
    WorldRuleRead,
    WorldRuleUpdate,
)
from novelforge.canon.service import (
    create_entity,
    delete_entity,
    ensure_novel_access,
    get_entity,
    list_entities,
    update_entity,
)
from novelforge.canon.state_schemas import (
    CharacterStateAtRead,
    CharacterStateCreate,
    CharacterStateRead,
    RelationshipCreate,
    RelationshipRead,
    StoryEventCreate,
    StoryEventRead,
)
from novelforge.canon.state_service import (
    create_character_state,
    create_relationship,
    create_story_event,
    get_character_state_at,
    list_character_states,
    list_character_states_at,
    list_relationships,
    list_story_events,
)
from novelforge.database import get_db
from novelforge.identity.dependencies import get_current_user, require_csrf
from novelforge.identity.models import User

router = APIRouter(prefix="/novels/{novel_id}", tags=["canon"])


@router.get("/events", response_model=list[StoryEventRead])
def get_story_events(
    novel_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[StoryEvent]:
    ensure_novel_access(db, user, novel_id)
    return list_story_events(db, novel_id)


@router.post("/events", response_model=StoryEventRead, status_code=status.HTTP_201_CREATED)
def post_story_event(
    novel_id: UUID,
    payload: StoryEventCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> StoryEvent:
    ensure_novel_access(db, user, novel_id)
    return create_story_event(db, novel_id, payload)


@router.get("/characters/{entity_id}/states", response_model=list[CharacterStateRead])
def get_character_states(
    novel_id: UUID,
    entity_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CharacterState]:
    ensure_novel_access(db, user, novel_id)
    return list_character_states(db, novel_id, entity_id)


@router.post(
    "/characters/{entity_id}/states",
    response_model=CharacterStateRead,
    status_code=status.HTTP_201_CREATED,
)
def post_character_state(
    novel_id: UUID,
    entity_id: UUID,
    payload: CharacterStateCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> CharacterState:
    ensure_novel_access(db, user, novel_id)
    return create_character_state(db, novel_id, entity_id, payload)


@router.get("/characters/{entity_id}/state-at", response_model=CharacterStateAtRead)
def get_character_state_at_order(
    novel_id: UUID,
    entity_id: UUID,
    story_order: Annotated[Decimal, Query(ge=0, max_digits=20, decimal_places=6)],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, UUID | Decimal | CharacterState | None]:
    ensure_novel_access(db, user, novel_id)
    state = get_character_state_at(db, novel_id, entity_id, story_order)
    return {"character_id": entity_id, "story_order": story_order, "state": state}


@router.get("/character-states", response_model=list[CharacterStateRead])
def get_character_states_at_order(
    novel_id: UUID,
    story_order: Annotated[Decimal, Query(ge=0, max_digits=20, decimal_places=6)],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CharacterState]:
    ensure_novel_access(db, user, novel_id)
    return list_character_states_at(db, novel_id, story_order)


@router.get("/relationships", response_model=list[RelationshipRead])
def get_relationships(
    novel_id: UUID,
    story_order: Annotated[Decimal | None, Query(ge=0, max_digits=20, decimal_places=6)] = None,
    include_non_canon: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Relationship]:
    ensure_novel_access(db, user, novel_id)
    return list_relationships(db, novel_id, story_order, include_non_canon)


@router.post("/relationships", response_model=RelationshipRead, status_code=status.HTTP_201_CREATED)
def post_relationship(
    novel_id: UUID,
    payload: RelationshipCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> Relationship:
    ensure_novel_access(db, user, novel_id)
    return create_relationship(db, novel_id, payload)


@router.get("/characters", response_model=list[CharacterRead])
def get_characters(
    novel_id: UUID,
    include_non_canon: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Character]:
    return list_entities(db, user, novel_id, Character, include_non_canon)


@router.post("/characters", response_model=CharacterRead, status_code=status.HTTP_201_CREATED)
def post_character(
    novel_id: UUID,
    payload: CharacterCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> Character:
    return create_entity(db, user, novel_id, Character, payload.model_dump())


@router.get("/characters/{entity_id}", response_model=CharacterRead)
def get_character(
    novel_id: UUID,
    entity_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Character:
    ensure_novel_access(db, user, novel_id)
    return get_entity(db, novel_id, entity_id, Character)


@router.patch("/characters/{entity_id}", response_model=CharacterRead)
def patch_character(
    novel_id: UUID,
    entity_id: UUID,
    payload: CharacterUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> Character:
    ensure_novel_access(db, user, novel_id)
    entity = get_entity(db, novel_id, entity_id, Character)
    return update_entity(db, entity, payload.model_dump(exclude_unset=True))


@router.delete("/characters/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_character(
    novel_id: UUID,
    entity_id: UUID,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> Response:
    ensure_novel_access(db, user, novel_id)
    delete_entity(db, get_entity(db, novel_id, entity_id, Character))
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/locations", response_model=list[LocationRead])
def get_locations(
    novel_id: UUID,
    include_non_canon: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Location]:
    return list_entities(db, user, novel_id, Location, include_non_canon)


@router.post("/locations", response_model=LocationRead, status_code=status.HTTP_201_CREATED)
def post_location(
    novel_id: UUID,
    payload: LocationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> Location:
    return create_entity(db, user, novel_id, Location, payload.model_dump())


@router.get("/locations/{entity_id}", response_model=LocationRead)
def get_location(
    novel_id: UUID,
    entity_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Location:
    ensure_novel_access(db, user, novel_id)
    return get_entity(db, novel_id, entity_id, Location)


@router.patch("/locations/{entity_id}", response_model=LocationRead)
def patch_location(
    novel_id: UUID,
    entity_id: UUID,
    payload: LocationUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> Location:
    ensure_novel_access(db, user, novel_id)
    entity = get_entity(db, novel_id, entity_id, Location)
    return update_entity(db, entity, payload.model_dump(exclude_unset=True))


@router.delete("/locations/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_location(
    novel_id: UUID,
    entity_id: UUID,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> Response:
    ensure_novel_access(db, user, novel_id)
    delete_entity(db, get_entity(db, novel_id, entity_id, Location))
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/factions", response_model=list[FactionRead])
def get_factions(
    novel_id: UUID,
    include_non_canon: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Faction]:
    return list_entities(db, user, novel_id, Faction, include_non_canon)


@router.post("/factions", response_model=FactionRead, status_code=status.HTTP_201_CREATED)
def post_faction(
    novel_id: UUID,
    payload: FactionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> Faction:
    return create_entity(db, user, novel_id, Faction, payload.model_dump())


@router.get("/factions/{entity_id}", response_model=FactionRead)
def get_faction(
    novel_id: UUID,
    entity_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Faction:
    ensure_novel_access(db, user, novel_id)
    return get_entity(db, novel_id, entity_id, Faction)


@router.patch("/factions/{entity_id}", response_model=FactionRead)
def patch_faction(
    novel_id: UUID,
    entity_id: UUID,
    payload: FactionUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> Faction:
    ensure_novel_access(db, user, novel_id)
    entity = get_entity(db, novel_id, entity_id, Faction)
    return update_entity(db, entity, payload.model_dump(exclude_unset=True))


@router.delete("/factions/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_faction(
    novel_id: UUID,
    entity_id: UUID,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> Response:
    ensure_novel_access(db, user, novel_id)
    delete_entity(db, get_entity(db, novel_id, entity_id, Faction))
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/world-rules", response_model=list[WorldRuleRead])
def get_world_rules(
    novel_id: UUID,
    include_non_canon: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WorldRule]:
    return list_entities(db, user, novel_id, WorldRule, include_non_canon)


@router.post("/world-rules", response_model=WorldRuleRead, status_code=status.HTTP_201_CREATED)
def post_world_rule(
    novel_id: UUID,
    payload: WorldRuleCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> WorldRule:
    return create_entity(db, user, novel_id, WorldRule, payload.model_dump())


@router.get("/world-rules/{entity_id}", response_model=WorldRuleRead)
def get_world_rule(
    novel_id: UUID,
    entity_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorldRule:
    ensure_novel_access(db, user, novel_id)
    return get_entity(db, novel_id, entity_id, WorldRule)


@router.patch("/world-rules/{entity_id}", response_model=WorldRuleRead)
def patch_world_rule(
    novel_id: UUID,
    entity_id: UUID,
    payload: WorldRuleUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> WorldRule:
    ensure_novel_access(db, user, novel_id)
    entity = get_entity(db, novel_id, entity_id, WorldRule)
    return update_entity(db, entity, payload.model_dump(exclude_unset=True))


@router.delete("/world-rules/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_world_rule(
    novel_id: UUID,
    entity_id: UUID,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> Response:
    ensure_novel_access(db, user, novel_id)
    delete_entity(db, get_entity(db, novel_id, entity_id, WorldRule))
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
