import pytest
from pydantic import ValidationError

from manual_assistant.infrastructure.settings import Settings


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("APP_ENVIRONMENT", "APP_CORS_ORIGINS", "APP_DB_HOST", "APP_DB_PASSWORD"):
        monkeypatch.delenv(name, raising=False)


def test_reads_cors_origins_as_comma_separated_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_CORS_ORIGINS", "http://servidor, http://servidor:8080 ,")

    settings = Settings(
        _env_file=None,
        db_password="segredo",
        auth_secret_key="segredo-de-teste-com-mais-de-32-caracteres",
    )

    assert settings.cors_origins == ["http://servidor", "http://servidor:8080"]


def test_uses_development_defaults() -> None:
    settings = Settings(
        _env_file=None,
        db_password="segredo",
        auth_secret_key="segredo-de-teste-com-mais-de-32-caracteres",
    )

    assert settings.environment == "development"
    assert settings.cors_origins == ["http://localhost:5173"]


def test_thinking_budget_can_be_disabled_with_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_GEMINI_THINKING_BUDGET", "none")

    assert (
        Settings(
            _env_file=None,
            db_password="x",
            auth_secret_key="segredo-de-teste-com-mais-de-32-caracteres",
        ).gemini_thinking_budget
        is None
    )


def test_requires_a_database_password() -> None:
    with pytest.raises(ValidationError, match="db_password"):
        Settings(_env_file=None, auth_secret_key="segredo-de-teste-com-mais-de-32-caracteres")


def test_requires_a_strong_session_secret() -> None:
    with pytest.raises(ValidationError, match="32 caracteres"):
        Settings(_env_file=None, db_password="x", auth_secret_key="curta")


def test_builds_database_url_without_leaking_the_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_DB_HOST", "db")
    monkeypatch.setenv("APP_DB_PASSWORD", "s3nh@:forte")
    monkeypatch.setenv("APP_AUTH_SECRET_KEY", "x" * 32)

    settings = Settings(_env_file=None)

    assert settings.database_url.password == "s3nh@:forte"
    assert str(settings.database_url) == "postgresql+asyncpg://manuais:***@db:5432/manuais"
    assert "s3nh" not in repr(settings)
