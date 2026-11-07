from pathlib import Path
from tempfile import TemporaryDirectory

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command


def test_canon_migration_up_down_up(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    api_root = Path(__file__).resolve().parents[1]
    with TemporaryDirectory(prefix="novelforge-migration-") as temp_dir:
        database_path = Path(temp_dir) / "migration.db"
        config = Config(str(api_root / "alembic.ini"))
        config.set_main_option("script_location", str(api_root / "alembic"))
        config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")

        command.upgrade(config, "head")
        engine = create_engine(f"sqlite:///{database_path}")
        inspector = inspect(engine)
        assert {"characters", "locations", "factions", "world_rules"}.issubset(
            set(inspector.get_table_names())
        )

        command.downgrade(config, "20261107_0001")
        inspector = inspect(engine)
        assert not {"characters", "locations", "factions", "world_rules"}.intersection(
            inspector.get_table_names()
        )

        command.upgrade(config, "head")
        inspector = inspect(engine)
        assert {"characters", "locations", "factions", "world_rules"}.issubset(
            set(inspector.get_table_names())
        )
        engine.dispose()
