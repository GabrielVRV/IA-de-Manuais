import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from manual_assistant.domain.user import UserRole
from tests.http_app import FakeBackend
from tests.pdf_builder import build_pdf

URL = "/api/v1/sync"
PDF = build_pdf("Manual do Silo\nCapacidade: 500 t")


@pytest.fixture
def backend() -> FakeBackend:
    return FakeBackend()


def wait_until_finished(client: TestClient) -> dict[str, Any]:
    for _ in range(500):
        body: dict[str, Any] = client.get(URL).json()
        if not body["running"]:
            return body
        time.sleep(0.01)
    raise AssertionError("a sincronização não terminou")


def test_status_without_any_sync(backend: FakeBackend) -> None:
    client = backend.client_logged_in_as()

    assert client.get(URL).json() == {"enabled": True, "running": False, "last_run": None}


def test_check_shows_the_plan_without_changing_anything(backend: FakeBackend) -> None:
    assert backend.manual_source is not None
    backend.manual_source.put("ARMAZENAGEM/95000001-00P.pdf", PDF, title="SILO 500 T")
    backend.manual_source.put("ARMAZENAGEM/95000001-00E.pdf", PDF)
    client = backend.client_logged_in_as()

    response = client.post(f"{URL}/check")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["counts"]["add"] == 1
    assert body["counts"]["ignore"] == 1
    assert body["to_index"] == 1
    assert {"action": "add", "file_name": "95000001-00P.pdf", "title": "SILO 500 T"}.items() <= (
        body["items"][-1].items()
    )
    assert backend.repository.manuals == {}


def test_runs_in_background_and_reports_the_result(backend: FakeBackend) -> None:
    assert backend.manual_source is not None
    backend.manual_source.put("ARMAZENAGEM/95000001-00P.pdf", PDF)
    backend.manual_source.put("ARMAZENAGEM/95000002-00P.pdf", b"isto nao e um pdf")
    client = backend.client_logged_in_as("admin")

    with client:  # mantém o loop da API vivo para a tarefa em segundo plano
        response = client.post(f"{URL}/run")
        assert response.status_code == 202, response.text
        assert response.json()["total"] == 2
        status = wait_until_finished(client)

    run = status["last_run"]
    assert (run["done"], run["succeeded"], run["error"]) == (2, 1, None)
    assert run["failures"][0]["file_name"] == "95000002-00P.pdf"
    assert run["started_by"]
    [manual] = backend.repository.manuals.values()
    assert manual.status.value == "indexed"


def test_empty_folder_is_reported_and_nothing_changes(backend: FakeBackend) -> None:
    client = backend.client_logged_in_as()

    response = client.post(f"{URL}/run")

    assert response.status_code == 503
    assert "vazia" in response.json()["detail"]


def test_disabled_without_a_folder() -> None:
    backend = FakeBackend(manual_source=None)
    client = backend.client_logged_in_as()

    assert client.get(URL).json()["enabled"] is False
    assert client.post(f"{URL}/check").status_code == 409


def test_only_admins(backend: FakeBackend) -> None:
    client = backend.client_logged_in_as("maria", role=UserRole.USER)

    assert client.get(URL).status_code == 403
    assert client.post(f"{URL}/check").status_code == 403
    assert client.post(f"{URL}/run").status_code == 403
