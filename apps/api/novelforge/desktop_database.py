"""Versioned SQLite initialization shared by source and frozen desktop runtimes."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import URL, Connection, inspect

from alembic import command
from novelforge.database import Base, create_database_engine
from novelforge.knowledge.fts import FTS_TABLES
from novelforge.projects import models_registry  # noqa: F401


def sqlite_url(database_path: Path) -> str:
    return URL.create("sqlite", database=str(database_path.resolve())).render_as_string(
        hide_password=False
    )


def _legacy_revision(connection: Connection, scripts: ScriptDirectory) -> str:
    """Recognize only complete, known create_all-era schemas, never guess from one table."""
    actual_tables = set(inspect(connection).get_table_names()) - {"alembic_version"} - FTS_TABLES
    scratch = create_database_engine("sqlite://")
    try:
        config = Config()
        config.set_main_option("script_location", str(scripts.dir))
        config.attributes["desktop_runtime"] = True
        with scratch.begin() as candidate:
            config.attributes["connection"] = candidate
            for revision in reversed(list(scripts.walk_revisions())):
                command.upgrade(config, revision.revision)
                expected = (
                    set(inspect(candidate).get_table_names()) - {"alembic_version"} - FTS_TABLES
                )
                if actual_tables == expected:
                    for name in actual_tables:
                        required = set(Base.metadata.tables[name].columns.keys())
                        found = {column["name"] for column in inspect(connection).get_columns(name)}
                        if not required.issubset(found):
                            raise RuntimeError(f"Legacy database has an unsupported schema: {name}")
                    return revision.revision
    finally:
        scratch.dispose()
    raise RuntimeError("Unrecognized legacy database; restore a backup or migrate it explicitly.")


def initialize_database(database_path: Path) -> Path | None:
    database_path = database_path.resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    config.attributes["desktop_runtime"] = True
    scripts = ScriptDirectory.from_config(config)
    engine = create_database_engine(sqlite_url(database_path))
    backup: Path | None = None
    try:
        with engine.connect() as connection:
            tables = set(inspect(connection).get_table_names()) - {"alembic_version"}
            current = MigrationContext.configure(connection).get_current_revision()
            legacy = _legacy_revision(connection, scripts) if tables and not current else None
            if current:
                scripts.get_revision(current)

        if tables and current != scripts.get_current_head():
            backup_dir = database_path.parent / "backups"
            backup_dir.mkdir(exist_ok=True)
            timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
            backup = backup_dir / f"novelforge-before-upgrade-{timestamp}.db"
            with sqlite3.connect(database_path) as source, sqlite3.connect(backup) as target:
                source.backup(target)
            backup.chmod(0o600)

        with engine.begin() as connection:
            config.attributes["connection"] = connection
            if legacy:
                command.stamp(config, legacy)
            command.upgrade(config, "head")
        with engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA journal_mode=WAL")
        database_path.chmod(0o600)
        return backup
    finally:
        engine.dispose()
