import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from novelforge.database import Base, create_database_engine, make_session_factory
from novelforge.main import create_app
from novelforge.projects import models_registry as _models_registry  # noqa: F401
from novelforge.settings import Settings


@pytest.fixture
def engine() -> Engine:
    test_engine = create_database_engine("sqlite://")
    Base.metadata.create_all(test_engine)
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def client(engine: Engine):
    app = create_app(
        Settings(database_url="sqlite://", session_cookie_secure=True),
        engine=engine,
    )
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


@pytest.fixture
def db_session(engine: Engine):
    session_factory = make_session_factory(engine)
    session: Session = session_factory()
    try:
        yield session
    finally:
        session.close()
