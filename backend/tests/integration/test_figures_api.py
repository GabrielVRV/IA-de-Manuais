"""Descrição das figuras escolhida por quem importa, na tela (ADR 0014)."""

import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from manual_assistant.application.errors import ExternalServiceError
from manual_assistant.domain.user import UserRole
from tests.http_app import FakeBackend
from tests.pdf_builder import build_pdf

URL = "/api/v1/manuals"
PDF = build_pdf("Manual da Prensa P-200", "Montagem do motor", "Fim")


@pytest.fixture
def backend() -> FakeBackend:
    backend = FakeBackend()
    backend.figure_renderer.figure_pages = [2, 3]
    return backend


def upload(client: TestClient, **form: str) -> dict[str, Any]:
    response = client.post(URL, files={"file": ("prensa.pdf", PDF, "application/pdf")}, data=form)
    assert response.status_code == 202, response.text
    body: dict[str, Any] = response.json()
    return body


def wait_for_figures(client: TestClient, manual_id: str) -> dict[str, Any]:
    for _ in range(500):
        body: dict[str, Any] = client.get(f"{URL}/{manual_id}").json()
        if not body["describing_figures"]:
            return body
        time.sleep(0.01)
    raise AssertionError("a descrição das figuras não terminou")


class TestOnImport:
    def test_upload_without_the_option_does_not_call_the_model(self, backend: FakeBackend) -> None:
        client = backend.client_logged_in_as("admin")

        manual = client.get(f"{URL}/{upload(client)['id']}").json()

        assert (manual["status"], manual["figure_count"]) == ("indexed", 0)
        assert backend.figure_model.requests == []

    def test_upload_describing_the_figures(self, backend: FakeBackend) -> None:
        client = backend.client_logged_in_as("admin")

        manual = client.get(f"{URL}/{upload(client, describe_figures='true')['id']}").json()

        assert (manual["status"], manual["figure_count"]) == ("indexed", 2)
        assert len(backend.figure_model.requests) == 2

    def test_reprocessing_describing_the_figures(self, backend: FakeBackend) -> None:
        client = backend.client_logged_in_as("admin")
        manual_id = upload(client)["id"]

        response = client.post(f"{URL}/{manual_id}/reindex", params={"describe_figures": True})

        assert response.status_code == 202, response.text
        assert client.get(f"{URL}/{manual_id}").json()["figure_count"] == 2


class TestIndexedManual:
    def test_shows_how_many_pages_would_be_described(self, backend: FakeBackend) -> None:
        client = backend.client_logged_in_as("admin")
        manual_id = upload(client)["id"]

        response = client.get(f"{URL}/{manual_id}/figures")

        assert response.status_code == 200, response.text
        assert response.json() == {"with_figures": 2, "pending": 2}
        assert backend.figure_model.requests == []

    def test_describes_the_figures_in_background(self, backend: FakeBackend) -> None:
        client = backend.client_logged_in_as("admin")
        manual_id = upload(client)["id"]
        text_chunks = len(backend.embeddings.embedded_texts)

        with client:  # mantém o loop da API vivo para a tarefa em segundo plano
            response = client.post(f"{URL}/{manual_id}/figures")
            assert response.status_code == 202, response.text
            manual = wait_for_figures(client, manual_id)

        assert (manual["figure_count"], manual["figures_described"]) == (2, 2)
        assert manual["figures_error"] is None
        assert len(backend.embeddings.embedded_texts) == text_chunks + 2
        assert client.get(f"{URL}/{manual_id}/figures").json()["pending"] == 0

    def test_reports_why_the_description_stopped(self, backend: FakeBackend) -> None:
        backend.figure_model.error = ExternalServiceError("cota excedida")
        client = backend.client_logged_in_as("admin")
        manual_id = upload(client)["id"]

        with client:
            client.post(f"{URL}/{manual_id}/figures")
            manual = wait_for_figures(client, manual_id)

        assert manual["figures_error"] == "cota excedida"

    def test_a_manual_that_failed_must_be_reprocessed(self, backend: FakeBackend) -> None:
        backend.embeddings.error = ExternalServiceError("instável")
        client = backend.client_logged_in_as("admin")
        manual_id = upload(client)["id"]

        assert client.post(f"{URL}/{manual_id}/figures").status_code == 409

    def test_only_admins(self, backend: FakeBackend) -> None:
        manual_id = upload(backend.client_logged_in_as("admin"))["id"]
        client = backend.client_logged_in_as("ana", role=UserRole.USER)

        assert client.get(f"{URL}/{manual_id}/figures").status_code == 403
        assert client.post(f"{URL}/{manual_id}/figures").status_code == 403


class TestSync:
    def test_sync_describing_the_figures(self, backend: FakeBackend) -> None:
        assert backend.manual_source is not None
        backend.manual_source.put("ARMAZENAGEM/95000001-00P.pdf", PDF)
        client = backend.client_logged_in_as("admin")

        with client:
            response = client.post("/api/v1/sync/run", params={"describe_figures": True})
            assert response.status_code == 202, response.text
            assert response.json()["describe_figures"] is True
            for _ in range(500):
                if not client.get("/api/v1/sync").json()["running"]:
                    break
                time.sleep(0.01)

        [manual] = backend.repository.manuals.values()
        assert manual.figure_count == 2

    def test_schedule_keeps_the_figure_option(self, backend: FakeBackend) -> None:
        client = backend.client_logged_in_as("admin")

        response = client.put(
            "/api/v1/sync/schedule",
            json={"enabled": True, "time": "00:00", "describe_figures": True},
        )

        assert response.status_code == 200, response.text
        assert client.get("/api/v1/sync/schedule").json()["describe_figures"] is True
