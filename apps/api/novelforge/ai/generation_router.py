from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from novelforge.ai.generation_schemas import GenerationAccept, GenerationCreate, GenerationRead
from novelforge.ai.generation_service import (
    accept_generation,
    cancel_generation,
    get_generation,
    start_generation,
)
from novelforge.database import get_db
from novelforge.identity.dependencies import get_current_user, get_settings, require_csrf
from novelforge.identity.models import User
from novelforge.projects.service import get_novel
from novelforge.settings import Settings

router = APIRouter(prefix="/novels/{novel_id}/ai/generations", tags=["ai-generations"])


@router.post("", response_model=GenerationRead, status_code=status.HTTP_202_ACCEPTED)
def post_generation(
    novel_id: UUID,
    payload: GenerationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
):
    return start_generation(db, user, novel_id, payload, settings)


@router.get("/{generation_id}", response_model=GenerationRead)
def get_generation_status(
    novel_id: UUID,
    generation_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_generation(db, user, novel_id, generation_id)


@router.post("/{generation_id}/cancel", response_model=GenerationRead)
def post_cancel(
    novel_id: UUID,
    generation_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    get_novel(db, user, novel_id)
    return cancel_generation(db, get_generation(db, user, novel_id, generation_id))


@router.post("/{generation_id}/accept")
def post_accept(
    novel_id: UUID,
    generation_id: UUID,
    payload: GenerationAccept,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    session = get_generation(db, user, novel_id, generation_id)
    chapter = accept_generation(db, user, session, payload.expected_version)
    response.headers["ETag"] = f'"{chapter.current_version}"'
    return {
        "generation_id": str(session.id),
        "chapter_id": str(chapter.id),
        "current_version": chapter.current_version,
    }
