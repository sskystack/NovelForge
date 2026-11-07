from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from novelforge.ai.analysis_schemas import ChapterAnalysisRead
from novelforge.ai.analysis_service import analyze_chapter_version
from novelforge.database import get_db
from novelforge.identity.dependencies import get_current_user, get_settings, require_csrf
from novelforge.identity.models import User
from novelforge.settings import Settings

router = APIRouter(prefix="/novels/{novel_id}/ai/analysis", tags=["ai-analysis"])


@router.post(
    "/{chapter_version_id}",
    response_model=ChapterAnalysisRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def post_analysis(
    novel_id: UUID,
    chapter_version_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
):
    return analyze_chapter_version(db, user, novel_id, chapter_version_id, settings)


@router.get("/{chapter_version_id}", response_model=ChapterAnalysisRead)
def get_analysis(
    novel_id: UUID,
    chapter_version_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from sqlalchemy import select

    from novelforge.ai.analysis_models import ChapterAnalysis
    from novelforge.projects.service import get_novel

    get_novel(db, user, novel_id)
    analysis = db.scalar(
        select(ChapterAnalysis).where(
            ChapterAnalysis.novel_id == novel_id,
            ChapterAnalysis.chapter_version_id == chapter_version_id,
        )
    )
    if analysis is None:
        from novelforge.errors import Problem

        raise Problem(
            404,
            "CHAPTER_ANALYSIS_NOT_FOUND",
            "Analysis not found",
            "No analysis exists for this chapter version.",
        )
    return analysis
