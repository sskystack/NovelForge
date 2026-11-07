from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from novelforge.database import get_db
from novelforge.identity.dependencies import get_current_user, require_csrf
from novelforge.identity.models import User
from novelforge.projects.models import Novel
from novelforge.projects.schemas import NovelCreate, NovelRead, NovelUpdate
from novelforge.projects.service import (
    archive_novel,
    create_novel,
    get_novel,
    list_novels,
    update_novel,
)

router = APIRouter(prefix="/novels", tags=["projects"])


@router.get("", response_model=list[NovelRead])
def get_novels(
    include_archived: bool = Query(default=False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Novel]:
    return list_novels(db, user, include_archived)


@router.post("", response_model=NovelRead, status_code=status.HTTP_201_CREATED)
def post_novel(
    payload: NovelCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> Novel:
    return create_novel(db, user, payload)


@router.get("/{novel_id}", response_model=NovelRead)
def get_novel_by_id(
    novel_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Novel:
    return get_novel(db, user, novel_id)


@router.patch("/{novel_id}", response_model=NovelRead)
def patch_novel(
    novel_id: UUID,
    payload: NovelUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> Novel:
    novel = get_novel(db, user, novel_id)
    return update_novel(db, novel, payload)


@router.delete("/{novel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_novel(
    novel_id: UUID,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> Response:
    novel = get_novel(db, user, novel_id)
    archive_novel(db, novel)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
