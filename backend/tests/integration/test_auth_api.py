import pytest
from fastapi.testclient import TestClient

from manual_assistant.domain.user import UserRole
from tests.http_app import FakeBackend, login
from tests.pdf_builder import build_pdf
from tests.security import DEFAULT_PASSWORD

AUTH = "/api/v1/auth"


@pytest.fixture
def backend() -> FakeBackend:
    return FakeBackend()


class TestLogin:
    def test_sets_an_http_only_session_cookie(self, backend: FakeBackend) -> None:
        backend.add_user("maria")
        client = TestClient(backend.build_app())

        response = client.post(
            f"{AUTH}/login", json={"username": "Maria", "password": DEFAULT_PASSWORD}
        )

        assert response.status_code == 200
        assert response.json()["username"] == "maria"
        cookie = response.headers["set-cookie"]
        assert "ma_session=" in cookie
        assert "HttpOnly" in cookie
        assert "SameSite=lax" in cookie
        assert DEFAULT_PASSWORD not in response.text
        assert "password_hash" not in response.text

    @pytest.mark.parametrize("username", ["maria", "nao-existe"])
    def test_wrong_credentials_get_the_same_answer(
        self, backend: FakeBackend, username: str
    ) -> None:
        backend.add_user("maria")

        response = TestClient(backend.build_app()).post(
            f"{AUTH}/login", json={"username": username, "password": "errada-123"}
        )

        assert response.status_code == 401
        assert response.json() == {"detail": "Usuário ou senha inválidos"}

    def test_blocks_brute_force(self, backend: FakeBackend) -> None:
        backend.add_user("maria")
        client = TestClient(backend.build_app())
        for _ in range(4):
            client.post(f"{AUTH}/login", json={"username": "maria", "password": "errada-123"})

        response = client.post(
            f"{AUTH}/login", json={"username": "maria", "password": "errada-123"}
        )

        assert response.status_code == 429
        assert "Tente novamente" in response.json()["detail"]

    def test_logout_ends_the_session(self, backend: FakeBackend) -> None:
        client = backend.client_logged_in_as("maria", role=UserRole.USER)

        client.post(f"{AUTH}/logout")

        assert client.get(f"{AUTH}/me").status_code == 401


class TestAccessControl:
    @pytest.mark.parametrize(
        ("method", "path"),
        [("get", "/api/v1/manuals"), ("post", "/api/v1/questions"), ("get", "/api/v1/users")],
    )
    def test_requires_login(self, backend: FakeBackend, method: str, path: str) -> None:
        response = getattr(TestClient(backend.build_app()), method)(path)

        assert response.status_code == 401
        assert response.json() == {"detail": "Faça login para continuar"}

    def test_health_check_stays_public(self, backend: FakeBackend) -> None:
        assert TestClient(backend.build_app()).get("/api/v1/health").status_code == 200

    def test_regular_users_can_ask_and_browse_but_not_change_manuals(
        self, backend: FakeBackend
    ) -> None:
        client = backend.client_logged_in_as("joao", role=UserRole.USER)
        pdf = {"file": ("m.pdf", build_pdf("Conteúdo"), "application/pdf")}

        assert client.get("/api/v1/manuals").status_code == 200
        assert client.post("/api/v1/questions", json={"question": "Pressão?"}).status_code == 200
        assert client.post("/api/v1/manuals", files=pdf).status_code == 403
        assert client.get("/api/v1/users").status_code == 403

    def test_a_temporary_password_must_be_changed_first(self, backend: FakeBackend) -> None:
        backend.add_user("ana", must_change_password=True)
        client = TestClient(backend.build_app())
        login(client, "ana")

        blocked = client.post("/api/v1/questions", json={"question": "Pressão?"})
        assert blocked.status_code == 403
        assert "Troque sua senha" in blocked.json()["detail"]
        assert client.get(f"{AUTH}/me").json()["must_change_password"] is True

        changed = client.post(
            f"{AUTH}/change-password",
            json={"current_password": DEFAULT_PASSWORD, "new_password": "minha-nova-senha"},
        )

        assert changed.status_code == 204
        assert client.post("/api/v1/questions", json={"question": "Pressão?"}).status_code == 200

    def test_deactivating_a_user_ends_their_session_immediately(self, backend: FakeBackend) -> None:
        client = backend.client_logged_in_as("joao", role=UserRole.USER)
        user = next(u for u in backend.users.users.values() if u.username == "joao")

        user.deactivate()

        assert client.get("/api/v1/manuals").status_code == 401


class TestUserAdministration:
    def test_admin_manages_users(self, backend: FakeBackend) -> None:
        client = backend.client_logged_in_as("admin")

        created = client.post(
            "/api/v1/users",
            json={
                "username": "maria.silva",
                "display_name": "Maria Silva",
                "temporary_password": "provisoria-1",
            },
        )
        assert created.status_code == 201
        user = created.json()
        assert (user["role"], user["must_change_password"]) == ("user", True)

        assert (
            client.post(
                "/api/v1/users",
                json={
                    "username": "maria.silva",
                    "display_name": "Dup",
                    "temporary_password": "provisoria-1",
                },
            ).status_code
            == 409
        )

        reset = client.post(
            f"/api/v1/users/{user['id']}/reset-password",
            json={"temporary_password": "outra-senha-1"},
        )
        assert reset.status_code == 200

        deactivated = client.patch(f"/api/v1/users/{user['id']}", json={"is_active": False})
        assert deactivated.json()["is_active"] is False

        listed = client.get("/api/v1/users").json()
        assert {u["username"] for u in listed} == {"admin", "maria.silva"}

    def test_admin_cannot_deactivate_themselves(self, backend: FakeBackend) -> None:
        client = backend.client_logged_in_as("admin")
        me = client.get(f"{AUTH}/me").json()

        response = client.patch(f"/api/v1/users/{me['id']}", json={"is_active": False})

        assert response.status_code == 422
        assert "a si mesmo" in response.json()["detail"]
