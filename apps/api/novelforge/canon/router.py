from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from novelforge.canon.models import Character, Faction, Location, WorldRule
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
from novelforge.database import get_db
from novelforge.identity.dependencies import get_current_user, require_csrf
from novelforge.identity.models import User

router = APIRouter(prefix="/novels/{novel_id}", tags=["canon"])


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
