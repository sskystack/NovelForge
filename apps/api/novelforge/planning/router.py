from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.orm import Session

from novelforge.database import get_db
from novelforge.errors import Problem
from novelforge.identity.dependencies import get_current_user, require_csrf
from novelforge.identity.models import User
from novelforge.planning.models import Chapter, OutlineNode
from novelforge.planning.schemas import (
    ChapterCreate,
    ChapterPage,
    ChapterRead,
    ChapterUpdate,
    ChapterVersionRead,
    OutlineNodeCreate,
    OutlineNodeRead,
    OutlineNodeUpdate,
    OutlineReorder,
)
from novelforge.planning.service import (
    create_chapter,
    create_outline_node,
    delete_chapter,
    delete_outline_node,
    get_chapter,
    get_outline_node,
    list_chapter_versions,
    list_chapters,
    list_outline_tree,
    reorder_outline_nodes,
    restore_chapter_version,
    update_chapter,
    update_outline_node,
)
from novelforge.projects.service import get_novel

router = APIRouter(prefix="/novels/{novel_id}", tags=["planning"])


@router.get("/outlines", response_model=list[OutlineNodeRead])
def get_outlines(
    novel_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[OutlineNodeRead]:
    return list_outline_tree(db, user, novel_id)


@router.post("/outlines", response_model=OutlineNodeRead, status_code=status.HTTP_201_CREATED)
def post_outline(
    novel_id: UUID,
    payload: OutlineNodeCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> OutlineNode:
    return create_outline_node(db, user, novel_id, payload)


@router.post("/outlines/reorder", response_model=list[OutlineNodeRead])
def post_outline_reorder(
    novel_id: UUID,
    payload: OutlineReorder,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> list[OutlineNode]:
    return reorder_outline_nodes(
        db,
        user,
        novel_id,
        payload.parent_id,
        payload.ordered_node_ids,
    )


@router.get("/outlines/{node_id}", response_model=OutlineNodeRead)
def get_outline(
    novel_id: UUID,
    node_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OutlineNode:
    get_novel(db, user, novel_id)
    return get_outline_node(db, novel_id, node_id)


@router.patch("/outlines/{node_id}", response_model=OutlineNodeRead)
def patch_outline(
    novel_id: UUID,
    node_id: UUID,
    payload: OutlineNodeUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> OutlineNode:
    return update_outline_node(db, user, novel_id, node_id, payload)


@router.delete("/outlines/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_outline(
    novel_id: UUID,
    node_id: UUID,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> Response:
    delete_outline_node(db, user, novel_id, node_id)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/chapters", response_model=ChapterPage)
def get_chapters(
    novel_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChapterPage:
    return list_chapters(db, user, novel_id, limit, cursor)


@router.post("/chapters", response_model=ChapterRead, status_code=status.HTTP_201_CREATED)
def post_chapter(
    novel_id: UUID,
    payload: ChapterCreate,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> Chapter:
    chapter = create_chapter(db, user, novel_id, payload)
    response.headers["ETag"] = f'"{chapter.current_version}"'
    return chapter


@router.get("/chapters/{chapter_id}", response_model=ChapterRead)
def get_chapter_by_id(
    novel_id: UUID,
    chapter_id: UUID,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Chapter:
    chapter = get_chapter(db, user, novel_id, chapter_id)
    response.headers["ETag"] = f'"{chapter.current_version}"'
    return chapter


@router.get("/chapters/{chapter_id}/versions", response_model=list[ChapterVersionRead])
def get_chapter_versions(
    novel_id: UUID,
    chapter_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChapterVersionRead]:
    return list_chapter_versions(db, user, novel_id, chapter_id)


@router.patch("/chapters/{chapter_id}", response_model=ChapterRead)
def patch_chapter(
    novel_id: UUID,
    chapter_id: UUID,
    payload: ChapterUpdate,
    response: Response,
    if_match: str = Header(alias="If-Match"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> Chapter:
    chapter = get_chapter(db, user, novel_id, chapter_id)
    updated = update_chapter(db, user, chapter, payload, _parse_if_match(if_match))
    response.headers["ETag"] = f'"{updated.current_version}"'
    return updated


@router.post(
    "/chapters/{chapter_id}/restore/{version_id}",
    response_model=ChapterRead,
)
def post_restore_chapter_version(
    novel_id: UUID,
    chapter_id: UUID,
    version_id: UUID,
    response: Response,
    if_match: str = Header(alias="If-Match"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> Chapter:
    chapter = get_chapter(db, user, novel_id, chapter_id)
    restored = restore_chapter_version(
        db,
        user,
        chapter,
        version_id,
        _parse_if_match(if_match),
    )
    response.headers["ETag"] = f'"{restored.current_version}"'
    return restored


@router.delete("/chapters/{chapter_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_chapter(
    novel_id: UUID,
    chapter_id: UUID,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
) -> Response:
    delete_chapter(db, get_chapter(db, user, novel_id, chapter_id))
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


def _parse_if_match(value: str) -> int:
    candidate = value.strip()
    if candidate.startswith("W/") or "," in candidate or candidate == "*":
        raise Problem(
            400,
            "INVALID_IF_MATCH",
            "Invalid If-Match",
            "Provide one strong chapter version ETag.",
        )
    if len(candidate) >= 2 and candidate[0] == '"' and candidate[-1] == '"':
        candidate = candidate[1:-1]
    try:
        version = int(candidate)
    except ValueError as error:
        raise Problem(
            400,
            "INVALID_IF_MATCH",
            "Invalid If-Match",
            "If-Match must contain a chapter version number.",
        ) from error
    if version < 0:
        raise Problem(
            400,
            "INVALID_IF_MATCH",
            "Invalid If-Match",
            "Chapter version cannot be negative.",
        )
    return version
