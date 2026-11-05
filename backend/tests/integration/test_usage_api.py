from fastapi.testclient import TestClient

from manual_assistant.domain.chunk import ScoredChunk
from manual_assistant.domain.user import UserRole
from tests.factories import make_chunk, make_manual
from tests.http_app import FakeBackend, login

URL = "/api/v1/usage"


def backend_with_answers() -> FakeBackend:
    backend = FakeBackend()
    backend.vector_store.search_results = [ScoredChunk(make_chunk(make_manual()), 0.9)]
    backend.language_model.answer = "Resposta [1]."
    return backend


def ask(client: TestClient, question: str = "Qual a pressão?") -> None:
    response = client.post("/api/v1/questions", json={"question": question})
    assert response.status_code == 200, response.text


def test_admin_sees_who_used_the_assistant_and_the_tokens_spent() -> None:
    backend = backend_with_answers()
    backend.add_user("maria")
    admin = backend.client_logged_in_as("admin")
    maria = TestClient(admin.app)
    login(maria, "maria")
    ask(maria)
    ask(maria)
    ask(admin)

    response = admin.get(URL, params={"days": 7})

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["by_day"]) == 7
    assert body["timezone"] == "America/Sao_Paulo"
    assert body["totals"]["questions"] == 3
    assert body["totals"]["total_tokens"] == 6  # o modelo falso gasta 1 + 1 por pergunta
    assert [(u["username"], u["totals"]["questions"]) for u in body["by_user"]] == [
        ("maria", 2),
        ("admin", 1),
    ]
    assert body["unpriced_models"] == ["fake-model"]


def test_cost_uses_the_price_registered_on_the_settings_screen() -> None:
    backend = backend_with_answers()
    admin = backend.client_logged_in_as("admin")
    ask(admin)

    saved = admin.put(
        "/api/v1/settings/model-prices",
        json={"model": "fake-model", "input_per_million": 5000, "output_per_million": 5000},
    )
    assert saved.status_code == 200, saved.text
    totals = admin.get(URL).json()["totals"]

    assert totals["cost_usd"] == 0.01  # (1 + 1 token) x 5000 dólares / milhão
    assert totals["cost_is_partial"] is False


def test_usage_never_exposes_the_question_text() -> None:
    backend = backend_with_answers()
    admin = backend.client_logged_in_as("admin")
    ask(admin, "Pergunta confidencial sobre a prensa")

    assert "confidencial" not in admin.get(URL).text


def test_only_admins_see_the_usage() -> None:
    client = FakeBackend().client_logged_in_as("maria", role=UserRole.USER)

    assert client.get(URL).status_code == 403


def test_rejects_an_invalid_period() -> None:
    client = FakeBackend().client_logged_in_as("admin")

    assert client.get(URL, params={"days": 0}).status_code == 422
