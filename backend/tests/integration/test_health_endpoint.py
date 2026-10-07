from fastapi.testclient import TestClient

from manual_assistant import __version__
from manual_assistant.application.use_cases.check_health import CheckHealthUseCase
from manual_assistant.presentation.http.app import create_http_app
from manual_assistant.presentation.http.dependencies import UseCases
from tests.fakes import FakeHealthIndicator

HEALTH_URL = "/api/v1/health"
FRONTEND_ORIGIN = "http://servidor-interno"


def make_client(*indicators: FakeHealthIndicator) -> TestClient:
    app = create_http_app(
        title="test",
        version=__version__,
        cors_origins=[FRONTEND_ORIGIN],
        use_cases=UseCases(check_health=CheckHealthUseCase(indicators)),
    )
    return TestClient(app)


def test_reports_healthy_when_all_dependencies_are_up() -> None:
    client = make_client(FakeHealthIndicator("database"))

    response = client.get(HEALTH_URL)

    assert response.status_code == 200
    assert response.json() == {
        "status": "up",
        "version": __version__,
        "components": {"database": "up"},
    }


def test_returns_503_when_a_dependency_is_down() -> None:
    client = make_client(FakeHealthIndicator("database", healthy=False))

    response = client.get(HEALTH_URL)

    assert response.status_code == 503
    assert response.json()["components"] == {"database": "down"}


def test_allows_cors_from_configured_frontend_origin() -> None:
    client = make_client()

    response = client.options(
        HEALTH_URL,
        headers={"Origin": FRONTEND_ORIGIN, "Access-Control-Request-Method": "GET"},
    )

    assert response.headers["access-control-allow-origin"] == FRONTEND_ORIGIN


def test_rejects_cors_from_unknown_origin() -> None:
    client = make_client()

    response = client.get(HEALTH_URL, headers={"Origin": "http://site-qualquer"})

    assert "access-control-allow-origin" not in response.headers
