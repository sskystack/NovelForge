import argparse
from pathlib import Path

from sqlalchemy.orm import Session

from novelforge.database import create_database_engine, make_session_factory
from novelforge.identity.models import User
from novelforge.projects.archive import export_novel, import_novel
from novelforge.projects.models_registry import (  # noqa: F401
    AnalysisProposal,
    CanonProposal,
    CanonRevision,
    Chapter,
    ChapterAnalysis,
    ChapterVersion,
    Character,
    CharacterState,
    ConsistencyIssue,
    Faction,
    GenerationSession,
    KnowledgeChunk,
    KnowledgeDocument,
    Location,
    OutlineNode,
    Relationship,
    StoryEvent,
    ToolCallAudit,
    WorldRule,
)
from novelforge.settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["export", "import"])
    parser.add_argument("archive")
    parser.add_argument("--novel-id")
    parser.add_argument("--user-id")
    args = parser.parse_args()
    settings = Settings()
    engine = create_database_engine(settings.database_url)
    session_factory = make_session_factory(engine)
    db: Session = session_factory()
    try:
        if args.operation == "export":
            if not args.novel_id or not args.user_id:
                parser.error("export requires --novel-id and --user-id")
            owner = db.get(User, args.user_id)
            if owner is None:
                parser.error("user not found")
            data = export_novel(db, owner, args.novel_id)
            Path(args.archive).write_bytes(data)
        else:
            if not args.user_id:
                parser.error("import requires --user-id")
            owner = db.get(User, args.user_id)
            if owner is None:
                parser.error("user not found")
            novel = import_novel(db, owner, Path(args.archive).read_bytes())
            print(novel.id)
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    main()
