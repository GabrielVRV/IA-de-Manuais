from datetime import UTC, datetime

from manual_assistant.domain.usage import QuestionUsage
from manual_assistant.domain.user import UserRole
from tests.http_app import FakeBackend

URL = "/api/v1/settings"
PRICES_URL = f"{URL}/model-prices"


def test_admin_reads_and_changes_the_usage_retention() -> None:
    client = FakeBackend().client_logged_in_as("admin")

    assert client.get(URL).json()["usage_retention_months"] == 12

    response = client.patch(URL, json={"usage_retention_months": 6})

    assert response.status_code == 200, response.text
    assert response.json()["usage_retention_months"] == 6
    assert response.json()["updated_by"]
    assert client.get(URL).json()["usage_retention_months"] == 6


def test_rejects_an_invalid_retention() -> None:
    client = FakeBackend().client_logged_in_as("admin")

    assert client.patch(URL, json={"usage_retention_months": -1}).status_code == 422


def test_lists_models_already_used_so_the_admin_can_price_them() -> None:
    backend = FakeBackend()
    client = backend.client_logged_in_as("admin")
    user = next(iter(backend.users.users.values()))
    backend.usage.records.append(
        QuestionUsage(user.id, datetime(2026, 11, 5, tzinfo=UTC), "gpt-4.1-mini", 10, 10)
    )

    assert client.get(PRICES_URL).json() == [
        {
            "model": "gpt-4.1-mini",
            "configured": False,
            "input_per_million": None,
            "output_per_million": None,
        }
    ]

    saved = client.put(
        PRICES_URL,
        json={"model": "gpt-4.1-mini", "input_per_million": 0.4, "output_per_million": 1.6},
    )

    assert saved.status_code == 200, saved.text
    assert client.get(PRICES_URL).json() == [
        {
            "model": "gpt-4.1-mini",
            "configured": True,
            "input_per_million": 0.4,
            "output_per_million": 1.6,
        }
    ]


def test_removes_the_price_of_a_model() -> None:
    client = FakeBackend().client_logged_in_as("admin")
    client.put(
        PRICES_URL, json={"model": "modelo-antigo", "input_per_million": 1, "output_per_million": 1}
    )

    response = client.delete(PRICES_URL, params={"model": "modelo-antigo"})

    assert response.status_code == 204
    assert client.get(PRICES_URL).json() == []


def test_rejects_a_negative_price() -> None:
    client = FakeBackend().client_logged_in_as("admin")

    response = client.put(
        PRICES_URL, json={"model": "gpt-4.1-mini", "input_per_million": -1, "output_per_million": 1}
    )

    assert response.status_code == 422


def test_only_admins_reach_the_settings() -> None:
    client = FakeBackend().client_logged_in_as("maria", role=UserRole.USER)

    assert client.get(URL).status_code == 403
    assert client.patch(URL, json={"usage_retention_months": 1}).status_code == 403
    assert client.get(PRICES_URL).status_code == 403
    assert (
        client.put(
            PRICES_URL, json={"model": "x", "input_per_million": 1, "output_per_million": 1}
        ).status_code
        == 403
    )
    assert client.delete(PRICES_URL, params={"model": "x"}).status_code == 403
