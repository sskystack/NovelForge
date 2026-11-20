"""Optional SQLite FTS5 adapter. ORM boundaries are rechecked for every hit.

The trigram tokenizer supports Chinese substrings as well as Latin text. Short
queries and SQLite builds without FTS5 fall back to the deterministic tokenizer.
"""

import re
import sqlite3
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

FTS_TABLES = {
    "knowledge_fts",
    "knowledge_fts_data",
    "knowledge_fts_idx",
    "knowledge_fts_content",
    "knowledge_fts_docsize",
    "knowledge_fts_config",
}


def create_index(connection) -> bool:
    if connection.dialect.name != "sqlite":
        return False
    try:
        connection.exec_driver_sql(
            "CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING "
            "fts5(chunk_id UNINDEXED, novel_id UNINDEXED, content, tokenize='trigram')"
        )
        connection.exec_driver_sql("""CREATE TRIGGER IF NOT EXISTS knowledge_fts_insert
            AFTER INSERT ON knowledge_chunks BEGIN
            INSERT INTO knowledge_fts(chunk_id, novel_id, content)
            VALUES (new.id, new.novel_id, new.content); END""")
        connection.exec_driver_sql("""CREATE TRIGGER IF NOT EXISTS knowledge_fts_delete
            AFTER DELETE ON knowledge_chunks BEGIN
            DELETE FROM knowledge_fts WHERE chunk_id=old.id; END""")
        connection.exec_driver_sql("""CREATE TRIGGER IF NOT EXISTS knowledge_fts_update
            AFTER UPDATE OF content, novel_id ON knowledge_chunks BEGIN
            DELETE FROM knowledge_fts WHERE chunk_id=old.id;
            INSERT INTO knowledge_fts(chunk_id, novel_id, content)
            VALUES (new.id, new.novel_id, new.content); END""")
        connection.exec_driver_sql("""INSERT INTO knowledge_fts(chunk_id, novel_id, content)
            SELECT id, novel_id, content FROM knowledge_chunks
            WHERE id NOT IN (SELECT chunk_id FROM knowledge_fts)""")
        return True
    except (DBAPIError, sqlite3.DatabaseError):
        return False


def drop_index(connection):
    if connection.dialect.name == "sqlite":
        for trigger in ("knowledge_fts_insert", "knowledge_fts_delete", "knowledge_fts_update"):
            connection.exec_driver_sql(f"DROP TRIGGER IF EXISTS {trigger}")
        connection.exec_driver_sql("DROP TABLE IF EXISTS knowledge_fts")


def ranking(
    db, novel_id: UUID, query: str, limit: int = 200, visibility: tuple = ("approved",)
) -> list[UUID]:
    if db.bind.dialect.name != "sqlite":
        return []
    # No raw user MATCH syntax. Quote terms, cap their number and length.
    terms = [term[:100] for term in re.findall(r"[\w]+", query) if len(term) >= 3][:20]
    if not terms or not visibility:
        return []
    expression = " OR ".join('"' + term.replace('"', '""') + '"' for term in terms)
    try:
        placeholders = ",".join(f":visibility_{index}" for index in range(len(visibility)))
        rows = db.execute(
            text(f"""SELECT f.chunk_id FROM knowledge_fts f
            JOIN knowledge_chunks c ON c.id=f.chunk_id AND c.novel_id=f.novel_id
            JOIN knowledge_documents d ON d.id=c.document_id AND d.novel_id=c.novel_id
            WHERE knowledge_fts MATCH :query AND f.novel_id=:novel
                AND c.novel_id=:novel AND d.novel_id=:novel AND c.is_active=1
                AND d.status='ready' AND d.visibility IN ({placeholders})
                AND NOT EXISTS (SELECT 1 FROM chapter_versions v
                    JOIN chapters ch ON ch.id=v.chapter_id AND ch.novel_id=v.novel_id
                    WHERE v.id=d.source_id AND v.novel_id=:novel
                        AND v.version_number != ch.current_version)
            ORDER BY bm25(knowledge_fts), f.chunk_id LIMIT :limit"""),
            {
                "query": expression,
                "novel": novel_id.hex,
                "limit": limit,
                **{f"visibility_{index}": value for index, value in enumerate(visibility)},
            },
        ).all()
        return [UUID(row[0]) for row in rows]
    except (DBAPIError, ValueError):
        return []
