import pytest
from pydantic import ValidationError

from manual_assistant.infrastructure.settings import Settings


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "APP_ENVIRONMENT",
        "APP_CORS_ORIGINS",
        "APP_DB_HOST",
        "APP_DB_PASSWORD",
        "APP_TOTVS_LOGIN_URL",
        "APP_SYNC_SOURCE_DIR",
        "APP_SYNC_LANGUAGES",
    ):
        monkeypatch.delenv(name, raising=False)


def test_reads_cors_origins_as_comma_separated_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_CORS_ORIGINS", "http://servidor, http://servidor:8080 ,")

    settings = Settings(_env_file=None, db_password="segredo")

    assert settings.cors_origins == ["http://servidor", "http://servidor:8080"]


def test_uses_development_defaults() -> None:
    settings = Settings(_env_file=None, db_password="segredo")

    assert settings.environment == "development"
    assert settings.cors_origins == ["http://localhost:5173"]
    assert (settings.auth_session_idle_days, settings.auth_session_max_days) == (7, 30)
    assert settings.totvs_login_url is None


def test_sync_is_off_by_default_and_imports_only_portuguese() -> None:
    settings = Settings(_env_file=None, db_password="x")

    assert settings.sync_source_dir is None
    assert settings.sync_languages == ["P"]


def test_reads_sync_languages_as_comma_separated_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_SYNC_LANGUAGES", "p, E ,")

    assert Settings(_env_file=None, db_password="x").sync_languages == ["P", "E"]


def test_a_blank_totvs_url_turns_the_totvs_login_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_TOTVS_LOGIN_URL", "  ")

    assert Settings(_env_file=None, db_password="x").totvs_login_url is None


def test_idle_timeout_cannot_exceed_the_maximum_age() -> None:
    with pytest.raises(ValidationError, match="IDLE_DAYS"):
        Settings(
            _env_file=None, db_password="x", auth_session_idle_days=40, auth_session_max_days=30
        )


def test_thinking_budget_can_be_disabled_with_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_GEMINI_THINKING_BUDGET", "none")

    assert Settings(_env_file=None, db_password="x").gemini_thinking_budget is None


def test_requires_a_database_password() -> None:
    with pytest.raises(ValidationError, match="db_password"):
        Settings(_env_file=None)


def test_builds_database_url_without_leaking_the_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_DB_HOST", "db")
    monkeypatch.setenv("APP_DB_PASSWORD", "s3nh@:forte")

    settings = Settings(_env_file=None)

    assert settings.database_url.password == "s3nh@:forte"
    assert str(settings.database_url) == "postgresql+asyncpg://manuais:***@db:5432/manuais"
    assert "s3nh" not in repr(settings)
