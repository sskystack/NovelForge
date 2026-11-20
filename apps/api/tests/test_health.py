from fastapi.testclient import TestClient

from novelforge.database import create_database_engine
from novelforge.main import app, create_app
from novelforge.settings import Settings


def test_health_returns_ok() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_returns_database_status() -> None:
    engine = create_database_engine("sqlite://")
    test_app = create_app(Settings(database_url="sqlite://"), engine=engine)
    try:
        response = TestClient(test_app).get("/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}
    finally:
        engine.dispose()
