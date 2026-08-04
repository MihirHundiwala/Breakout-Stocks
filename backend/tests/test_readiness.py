from fastapi.testclient import TestClient

from app.db.health import database_is_ready
from app.main import app


def override_database_readiness(value: bool):
    async def override() -> bool:
        return value

    return override


def test_readiness_returns_ok_when_database_is_available() -> None:
    app.dependency_overrides[database_is_ready] = (
        override_database_readiness(True)
    )

    try:
        with TestClient(app) as client:
            response = client.get("/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}


def test_readiness_returns_503_when_database_is_unavailable() -> None:
    app.dependency_overrides[database_is_ready] = (
        override_database_readiness(False)
    )

    try:
        with TestClient(app) as client:
            response = client.get("/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "database": "unavailable",
    }
