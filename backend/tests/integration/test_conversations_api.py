import pytest
from fastapi.testclient import TestClient

from manual_assistant.domain.chunk import ScoredChunk
from manual_assistant.domain.pages import PageRange
from tests.factories import make_chunk, make_manual
from tests.http_app import FakeBackend

URL = "/api/v1/conversations"
manual = make_manual("Manual da Prensa P-200")


@pytest.fixture
def backend() -> FakeBackend:
    backend = FakeBackend()
    backend.vector_store.search_results = [
        ScoredChunk(make_chunk(manual, text="Pressão: 180 bar.", pages=PageRange(12, 12)), 0.9)
    ]
    backend.language_model.answer = "A pressão máxima é 180 bar [1]."
    return backend


def ask(client: TestClient, question: str, conversation_id: str | None = None) -> str:
    response = client.post(
        "/api/v1/questions", json={"question": question, "conversation_id": conversation_id}
    )
    assert response.status_code == 200, response.text
    return str(response.json()["conversation"]["id"])


def test_lists_and_opens_the_users_conversations(backend: FakeBackend) -> None:
    client = backend.client_logged_in_as("maria")
    conversation_id = ask(client, "Qual a pressão máxima?")
    ask(client, "E a mínima?", conversation_id)

    listed = client.get(URL).json()
    opened = client.get(f"{URL}/{conversation_id}").json()

    assert [(c["id"], c["title"], c["exchange_count"]) for c in listed] == [
        (conversation_id, "Qual a pressão máxima?", 2)
    ]
    assert [e["question"] for e in opened["exchanges"]] == [
        "Qual a pressão máxima?",
        "E a mínima?",
    ]
    first_answer = opened["exchanges"][0]["answer"]
    assert first_answer["answer"] == "A pressão máxima é 180 bar."
    assert first_answer["found"] is True
    assert first_answer["citations"][0]["pages_label"] == "p. 12"


def test_renames_and_deletes(backend: FakeBackend) -> None:
    client = backend.client_logged_in_as("maria")
    conversation_id = ask(client, "Qual a pressão máxima?")

    renamed = client.patch(f"{URL}/{conversation_id}", json={"title": "Pressão da P-200"})
    deleted = client.delete(f"{URL}/{conversation_id}")

    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Pressão da P-200"
    assert deleted.status_code == 204
    assert client.get(URL).json() == []
    assert client.get(f"{URL}/{conversation_id}").status_code == 404


def test_rejects_an_empty_title(backend: FakeBackend) -> None:
    client = backend.client_logged_in_as("maria")
    conversation_id = ask(client, "Qual a pressão máxima?")

    response = client.patch(f"{URL}/{conversation_id}", json={"title": "   "})

    assert response.status_code == 422


def test_other_users_see_nothing(backend: FakeBackend) -> None:
    maria = backend.client_logged_in_as("maria")
    conversation_id = ask(maria, "Qual a pressão máxima?")
    joao = backend.client_logged_in_as("joao")

    assert joao.get(URL).json() == []
    assert joao.get(f"{URL}/{conversation_id}").status_code == 404
    assert joao.patch(f"{URL}/{conversation_id}", json={"title": "x"}).status_code == 404
    assert joao.delete(f"{URL}/{conversation_id}").status_code == 404
    assert len(maria.get(URL).json()) == 1


def test_requires_login(backend: FakeBackend) -> None:
    client = TestClient(backend.build_app())

    assert client.get(URL).status_code == 401
