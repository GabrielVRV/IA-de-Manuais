import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine

from manual_assistant import __version__
from manual_assistant.infrastructure.persistence.health import DatabaseHealthIndicator
from manual_assistant.infrastructure.settings import Settings
from manual_assistant.main import create_app

pytestmark = pytest.mark.db


@pytest.mark.anyio
async def test_reports_healthy_database(engine: AsyncEngine) -> None:
    assert await DatabaseHealthIndicator(engine).is_healthy()


def test_composed_app_reports_database_up(postgres_settings: Settings) -> None:
    with TestClient(create_app(postgres_settings)) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "up",
        "version": __version__,
        "components": {"database": "up"},
    }


def test_composed_app_reports_database_down(postgres_settings: Settings) -> None:
    unreachable = postgres_settings.model_copy(update={"db_host": "127.0.0.1", "db_port": 1})

    with TestClient(create_app(unreachable)) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.json()["components"] == {"database": "down"}
