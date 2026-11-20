import hashlib
import io
import json
import zipfile
from collections import defaultdict
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from novelforge.ai.analysis_models import ChapterAnalysis
from novelforge.ai.analysis_proposal_models import AnalysisProposal
from novelforge.ai.generation_models import GenerationSession
from novelforge.ai.tool_models import ToolCallAudit
from novelforge.canon.models import (
    CanonProposal,
    CanonRevision,
    Character,
    CharacterState,
    Faction,
    Location,
    Relationship,
    StoryEvent,
    WorldRule,
)
from novelforge.errors import Problem
from novelforge.identity.models import User
from novelforge.knowledge.models import KnowledgeChunk, KnowledgeDocument
from novelforge.planning.models import Chapter, ChapterVersion, OutlineNode
from novelforge.projects.models import Novel, NovelStatus

SCHEMA_VERSION = 1
MAX_ARCHIVE_BYTES = 25 * 1024 * 1024
MAX_EXPANDED_BYTES = 100 * 1024 * 1024
MAX_ENTRIES = 5000


def _json_value(value):
    if isinstance(value, UUID):
        return str(value)
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    return value


def _row(model, item):
    return {
        column.key: _json_value(getattr(item, column.key)) for column in model.__table__.columns
    }


def export_novel(db: Session, owner: User, novel_id: UUID) -> bytes:
    from novelforge.projects.service import get_novel

    novel = get_novel(db, owner, novel_id)
    tables = {
        "novel": [_row(Novel, novel)],
        "characters": [
            _row(Character, x)
            for x in db.scalars(select(Character).where(Character.novel_id == novel_id))
        ],
        "locations": [
            _row(Location, x)
            for x in db.scalars(select(Location).where(Location.novel_id == novel_id))
        ],
        "factions": [
            _row(Faction, x)
            for x in db.scalars(select(Faction).where(Faction.novel_id == novel_id))
        ],
        "world_rules": [
            _row(WorldRule, x)
            for x in db.scalars(select(WorldRule).where(WorldRule.novel_id == novel_id))
        ],
        "story_events": [
            _row(StoryEvent, x)
            for x in db.scalars(select(StoryEvent).where(StoryEvent.novel_id == novel_id))
        ],
        "character_states": [
            _row(CharacterState, x)
            for x in db.scalars(select(CharacterState).where(CharacterState.novel_id == novel_id))
        ],
        "relationships": [
            _row(Relationship, x)
            for x in db.scalars(select(Relationship).where(Relationship.novel_id == novel_id))
        ],
        "canon_proposals": [
            _row(CanonProposal, x)
            for x in db.scalars(select(CanonProposal).where(CanonProposal.novel_id == novel_id))
        ],
        "canon_revisions": [
            _row(CanonRevision, x)
            for x in db.scalars(select(CanonRevision).where(CanonRevision.novel_id == novel_id))
        ],
        "outline_nodes": [
            _row(OutlineNode, x)
            for x in db.scalars(select(OutlineNode).where(OutlineNode.novel_id == novel_id))
        ],
        "chapters": [
            _row(Chapter, x)
            for x in db.scalars(select(Chapter).where(Chapter.novel_id == novel_id))
        ],
        "chapter_versions": [
            _row(ChapterVersion, x)
            for x in db.scalars(select(ChapterVersion).where(ChapterVersion.novel_id == novel_id))
        ],
        "knowledge_documents": [
            _row(KnowledgeDocument, x)
            for x in db.scalars(
                select(KnowledgeDocument).where(KnowledgeDocument.novel_id == novel_id)
            )
        ],
        "knowledge_chunks": [],
        "generation_sessions": [
            _row(GenerationSession, x)
            for x in db.scalars(
                select(GenerationSession).where(GenerationSession.novel_id == novel_id)
            )
        ],
        "tool_call_audits": [
            _row(ToolCallAudit, x)
            for x in db.scalars(select(ToolCallAudit).where(ToolCallAudit.novel_id == novel_id))
        ],
        "chapter_analyses": [
            _row(ChapterAnalysis, x)
            for x in db.scalars(select(ChapterAnalysis).where(ChapterAnalysis.novel_id == novel_id))
        ],
        "analysis_proposals": [
            _row(AnalysisProposal, x)
            for x in db.scalars(
                select(AnalysisProposal).where(AnalysisProposal.novel_id == novel_id)
            )
        ],
    }
    # Embeddings are regenerable and intentionally omitted from portable archives.
    manifest = {"schema_version": SCHEMA_VERSION, "novel_id": str(novel_id), "files": {}}
    files = {
        f"data/{name}.json": json.dumps(
            rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        for name, rows in tables.items()
    }
    manifest["files"] = {
        name: hashlib.sha256(content).hexdigest() for name, content in files.items()
    }
    files["manifest.json"] = json.dumps(
        manifest, ensure_ascii=False, sort_keys=True, indent=2
    ).encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return output.getvalue()


def _validate_archive(data: bytes) -> tuple[dict, dict[str, bytes]]:
    if len(data) > MAX_ARCHIVE_BYTES:
        raise Problem(
            413,
            "ARCHIVE_TOO_LARGE",
            "Archive too large",
            "Compressed archive exceeds the upload limit.",
        )
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
        infos = archive.infolist()
        if len(infos) > MAX_ENTRIES:
            raise ValueError("too many entries")
        expanded = 0
        contents = {}
        for info in infos:
            path = info.filename
            if (
                path.startswith(("/", "\\"))
                or ".." in path.replace("\\", "/").split("/")
                or "\\" in path
            ):
                raise ValueError("unsafe archive path")
            if info.is_dir():
                continue
            expanded += info.file_size
            if expanded > MAX_EXPANDED_BYTES:
                raise Problem(
                    413,
                    "ARCHIVE_TOO_LARGE",
                    "Archive too large",
                    "Expanded archive exceeds the upload limit.",
                )
            contents[path] = archive.read(info)
        manifest = json.loads(contents["manifest.json"])
        if manifest.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported schema version")
        for name, digest in manifest["files"].items():
            content = contents.get(name)
            if content is None or hashlib.sha256(content).hexdigest() != digest:
                raise ValueError("checksum mismatch")
        return manifest, contents
    except Problem:
        raise
    except (zipfile.BadZipFile, KeyError, json.JSONDecodeError, ValueError, OSError) as error:
        raise Problem(422, "INVALID_ARCHIVE", "Invalid project archive", str(error)) from error


def import_novel(db: Session, owner: User, data: bytes) -> Novel:
    manifest, contents = _validate_archive(data)
    tables = {
        name.removeprefix("data/").removesuffix(".json"): json.loads(content)
        for name, content in contents.items()
        if name.startswith("data/") and name.endswith(".json")
    }
    novel_rows = tables.get("novel", [])
    if len(novel_rows) != 1:
        raise Problem(
            422,
            "INVALID_ARCHIVE",
            "Invalid project archive",
            "Archive must include exactly one novel record.",
        )
    old_novel_id = UUID(manifest["novel_id"])
    novel_data = novel_rows[0]
    if UUID(novel_data["id"]) != old_novel_id:
        raise Problem(
            422, "INVALID_ARCHIVE", "Invalid project archive", "Manifest and novel ID do not match."
        )

    # Remap every record ID before inserting so all cross-table references resolve locally.
    id_maps: dict[str, dict[str, str]] = defaultdict(dict)
    tables["novel"][0]["id"] = str(uuid4())
    new_novel_id = tables["novel"][0]["id"]
    for table, rows in tables.items():
        if table == "novel":
            continue
        for row in rows:
            old_id = str(row["id"])
            id_maps[table][old_id] = str(uuid4())
    novel = Novel(
        owner_user_id=owner.id,
        title=novel_data["title"],
        language=novel_data.get("language", "zh-CN"),
        genre=novel_data.get("genre", []),
        premise=novel_data.get("premise", ""),
        writing_preferences=novel_data.get("writing_preferences", {}),
        settings=novel_data.get("settings", {}),
        status=NovelStatus.ACTIVE,
    )
    db.add(novel)
    db.flush()
    new_novel_id = str(novel.id)

    def remap(row: dict, table: str) -> dict:
        output = dict(row)
        if "id" in output:
            output["id"] = id_maps[table].get(str(output["id"]), output["id"])
        output["novel_id"] = new_novel_id
        references = {
            "parent_id": "outline_nodes",
            "outline_node_id": "outline_nodes",
            "chapter_id": "chapters",
            "chapter_version_id": "chapter_versions",
            "character_id": "characters",
            "from_character_id": "characters",
            "to_character_id": "characters",
            "source_event_id": "story_events",
            "source_chapter_id": "chapters",
            "source_proposal_id": "canon_proposals",
            "entity_id": None,
            "document_id": "knowledge_documents",
        }
        for key, target in references.items():
            value = output.get(key)
            if value is None:
                continue
            if target is not None:
                output[key] = id_maps[target].get(str(value), value)
            elif table == "canon_proposals" and output.get("entity_type"):
                output[key] = (
                    value  # Entity IDs are kept as typed payload references in audit proposals.
                )
        for key in ("created_by", "reviewed_by", "actor_user_id", "owner_user_id"):
            if key in output:
                output[key] = owner.id if output[key] is not None else None
        return output

    db.flush()
    ordered = [
        ("characters", Character),
        ("locations", Location),
        ("factions", Faction),
        ("world_rules", WorldRule),
        ("story_events", StoryEvent),
        ("outline_nodes", OutlineNode),
        ("chapters", Chapter),
        ("chapter_versions", ChapterVersion),
        ("character_states", CharacterState),
        ("relationships", Relationship),
        ("canon_proposals", CanonProposal),
        ("canon_revisions", CanonRevision),
        ("knowledge_documents", KnowledgeDocument),
        ("knowledge_chunks", KnowledgeChunk),
        ("generation_sessions", GenerationSession),
        ("tool_call_audits", ToolCallAudit),
        ("chapter_analyses", ChapterAnalysis),
        ("analysis_proposals", AnalysisProposal),
    ]
    for table, model in ordered:
        rows = tables.get(table, [])
        for row in rows:
            values = remap(row, table)
            if table == "knowledge_chunks":
                values.pop("embedding", None)
                values["is_active"] = False
            elif table == "knowledge_documents":
                values["status"] = "pending"
            allowed = {column.key for column in model.__table__.columns}
            values = {key: value for key, value in values.items() if key in allowed}
            for column in model.__table__.columns:
                if column.key in values and values[column.key] is not None:
                    try:
                        if column.type.python_type is UUID and isinstance(values[column.key], str):
                            values[column.key] = UUID(values[column.key])
                        elif isinstance(values[column.key], str) and column.key.endswith(
                            ("_at", "_time")
                        ):
                            values[column.key] = datetime.fromisoformat(values[column.key])
                    except (NotImplementedError, ValueError):
                        pass
            try:
                db.add(model(**values))
            except (TypeError, ValueError) as error:
                raise Problem(
                    422,
                    "INVALID_ARCHIVE",
                    "Invalid project archive",
                    f"Invalid {table} record: {error}",
                ) from error
        db.flush()
    try:
        db.commit()
        db.refresh(novel)
        return novel
    except Exception as error:
        db.rollback()
        raise Problem(
            422,
            "INVALID_ARCHIVE",
            "Invalid project archive",
            "Archive records failed validation or contain broken references.",
        ) from error
