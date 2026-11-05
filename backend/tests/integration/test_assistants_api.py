from fastapi.testclient import TestClient

from manual_assistant.domain.user import UserRole
from tests.http_app import FakeBackend, login

URL = "/api/v1/assistants"
ACCESS_URL = f"{URL}/engenharia/access"
QUESTIONS = "/api/v1/questions"
GLPI = "Abra um chamado no GLPI pedindo acesso."


def restrict(admin: TestClient) -> None:
    response = admin.put(
        ACCESS_URL, json={"default_access": "restricted", "request_instructions": GLPI}
    )
    assert response.status_code == 200, response.text


def test_everyone_uses_the_engineering_assistant_by_default() -> None:
    client = FakeBackend().client_logged_in_as("maria", role=UserRole.USER)

    (engineering,) = client.get(URL).json()

    assert engineering["id"] == "engenharia"
    assert engineering["allowed"] is True
    assert client.post(QUESTIONS, json={"question": "Pressão máxima?"}).status_code == 200


def test_restricted_assistant_refuses_questions_and_says_how_to_ask() -> None:
    backend = FakeBackend()
    restrict(backend.client_logged_in_as("admin"))
    maria = backend.client_logged_in_as("maria", role=UserRole.USER)

    (engineering,) = maria.get(URL).json()
    refused = maria.post(QUESTIONS, json={"question": "Pressão máxima?"})

    assert engineering["allowed"] is False
    assert engineering["request_instructions"] == GLPI
    assert refused.status_code == 403
    assert refused.json()["detail"] == f"Você não tem acesso ao Assistente de Engenharia. {GLPI}"
    assert backend.usage.records == []  # recusada antes de gastar tokens


def test_restricted_assistant_also_hides_the_manual_pdfs() -> None:
    backend = FakeBackend()
    restrict(backend.client_logged_in_as("admin"))
    maria = backend.client_logged_in_as("maria", role=UserRole.USER)

    response = maria.get("/api/v1/manuals/00000000-0000-0000-0000-000000000000/file")

    assert response.status_code == 403


def test_admin_grants_one_user_while_the_assistant_is_restricted() -> None:
    backend = FakeBackend()
    admin = backend.client_logged_in_as("admin")
    restrict(admin)
    maria = backend.client_logged_in_as("maria", role=UserRole.USER)
    maria_id = next(u["id"] for u in admin.get("/api/v1/users").json() if u["username"] == "maria")

    granted = admin.put(
        f"/api/v1/users/{maria_id}/assistants/engenharia", json={"access": "granted"}
    )

    assert granted.status_code == 200, granted.text
    assert granted.json() == {"engenharia": "granted"}
    listed = next(u for u in admin.get("/api/v1/users").json() if u["id"] == maria_id)
    assert listed["assistant_access"] == {"engenharia": "granted"}
    assert maria.post(QUESTIONS, json={"question": "Pressão máxima?"}).status_code == 200

    back = admin.put(f"/api/v1/users/{maria_id}/assistants/engenharia", json={"access": None})
    assert back.json() == {}
    assert maria.post(QUESTIONS, json={"question": "Pressão máxima?"}).status_code == 403


def test_admin_reads_and_changes_the_policies() -> None:
    admin = FakeBackend().client_logged_in_as("admin")

    (before,) = admin.get(f"{URL}/access").json()
    restrict(admin)
    (after,) = admin.get(f"{URL}/access").json()

    assert (before["default_access"], before["request_instructions"]) == ("open", None)
    assert (after["default_access"], after["request_instructions"]) == ("restricted", GLPI)
    assert after["updated_by"]


def test_only_admins_manage_access() -> None:
    backend = FakeBackend()
    maria = backend.client_logged_in_as("maria", role=UserRole.USER)

    assert maria.get(f"{URL}/access").status_code == 403
    assert maria.put(ACCESS_URL, json={"default_access": "open"}).status_code == 403


def test_rejects_an_unknown_assistant() -> None:
    admin = FakeBackend().client_logged_in_as("admin")

    response = admin.put(f"{URL}/ti/access", json={"default_access": "open"})

    assert response.status_code == 422


def test_a_new_network_user_enters_without_waiting_for_approval() -> None:
    backend = FakeBackend()
    backend.directory.add("joao", "senha-de-rede")
    joao = TestClient(backend.build_app())

    login(joao, "joao", "senha-de-rede")

    assert joao.get(URL).json()[0]["allowed"] is True
