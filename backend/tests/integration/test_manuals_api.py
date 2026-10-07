from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from manual_assistant.application.errors import ExternalServiceError
from manual_assistant.domain.manual import ManualId, ManualStatus
from tests.http_app import FakeBackend
from tests.pdf_builder import build_pdf

URL = "/api/v1/manuals"
PDF = build_pdf("Manual da Prensa P-200\nPressão máxima: 180 bar", "Troca de óleo a cada 2000 h")


@pytest.fixture
def backend() -> FakeBackend:
    return FakeBackend()


@pytest.fixture
def client(backend: FakeBackend) -> TestClient:
    return TestClient(backend.build_app())


def upload(
    client: TestClient, content: bytes = PDF, name: str = "Manual_Prensa-P200.pdf", **form: str
) -> dict[str, object]:
    response = client.post(URL, files={"file": (name, content, "application/pdf")}, data=form)
    assert response.status_code == 202, response.text
    body: dict[str, object] = response.json()
    return body


class TestUpload:
    def test_accepts_the_pdf_and_indexes_it_in_background(
        self, client: TestClient, backend: FakeBackend
    ) -> None:
        accepted = upload(client)

        assert accepted["status"] == "processing"
        assert accepted["title"] == "Manual Prensa P200"
        # O TestClient executa as tarefas em segundo plano antes de devolver a resposta.
        indexed = client.get(f"{URL}/{accepted['id']}").json()
        assert indexed["status"] == "indexed"
        assert indexed["page_count"] == 2
        assert indexed["chunk_count"] >= 1
        assert "Pressão máxima: 180 bar" in backend.embeddings.embedded_texts[0]

    def test_uses_the_informed_title(self, client: TestClient) -> None:
        assert upload(client, title="Prensa hidráulica P-200")["title"] == "Prensa hidráulica P-200"

    def test_accepts_windows_paths_sent_by_old_browsers(self, client: TestClient) -> None:
        manual = upload(client, name="C:\\Users\\ana\\Manual Torno.pdf")

        assert manual["file_name"] == "Manual Torno.pdf"

    @pytest.mark.parametrize(
        ("content", "message"),
        [(b"PK\x03\x04", "não é um PDF"), (b"", "vazio")],
        ids=["nao-e-pdf", "vazio"],
    )
    def test_rejects_invalid_files(self, client: TestClient, content: bytes, message: str) -> None:
        response = client.post(URL, files={"file": ("m.pdf", content, "application/pdf")})

        assert response.status_code == 422
        assert message in response.json()["detail"]

    def test_rejects_files_over_the_limit(self, backend: FakeBackend) -> None:
        backend.max_upload_bytes = 1024 * 1024
        client = TestClient(backend.build_app())
        big = b"%PDF-" + b"0" * (1024 * 1024)

        response = client.post(URL, files={"file": ("m.pdf", big, "application/pdf")})

        assert response.status_code == 422
        assert "limite de 1 MB" in response.json()["detail"]

    def test_records_indexing_failures_on_the_manual(
        self, client: TestClient, backend: FakeBackend
    ) -> None:
        backend.embeddings.error = ExternalServiceError("Cota do Gemini excedida")

        manual = client.get(f"{URL}/{upload(client)['id']}").json()

        assert manual["status"] == "failed"
        assert "serviço externo" in manual["failure_reason"]


class TestQueries:
    def test_lists_manuals_newest_first(self, client: TestClient) -> None:
        first = upload(client, title="Primeiro")
        second = upload(client, title="Segundo")

        listed = client.get(URL).json()

        assert {m["id"] for m in listed} == {first["id"], second["id"]}

    def test_unknown_manual_returns_404(self, client: TestClient) -> None:
        response = client.get(f"{URL}/{uuid4()}")

        assert response.status_code == 404
        assert "não encontrado" in response.json()["detail"]

    def test_external_failures_return_503(self, client: TestClient, backend: FakeBackend) -> None:
        backend.repository.error_on_list = ExternalServiceError("Falha no banco de dados")

        response = client.get(URL)

        assert response.status_code == 503
        assert response.json() == {"detail": "Falha no banco de dados"}


class TestReindexAndDelete:
    def test_reindexes_a_failed_manual(self, client: TestClient, backend: FakeBackend) -> None:
        backend.embeddings.error = ExternalServiceError("instável")
        manual_id = upload(client)["id"]
        backend.embeddings.error = None

        response = client.post(f"{URL}/{manual_id}/reindex")

        assert response.status_code == 202
        assert client.get(f"{URL}/{manual_id}").json()["status"] == "indexed"

    def test_refuses_to_reindex_a_manual_in_processing(
        self, client: TestClient, backend: FakeBackend
    ) -> None:
        manual_id = upload(client)["id"]
        backend.repository.manuals[ManualId(UUID(str(manual_id)))].status = ManualStatus.PROCESSING

        response = client.post(f"{URL}/{manual_id}/reindex")

        assert response.status_code == 409

    def test_deletes_the_manual(self, client: TestClient, backend: FakeBackend) -> None:
        manual_id = upload(client)["id"]

        assert client.delete(f"{URL}/{manual_id}").status_code == 204
        assert client.get(f"{URL}/{manual_id}").status_code == 404
        assert backend.storage.files == {}
        assert backend.vector_store.items == {}
