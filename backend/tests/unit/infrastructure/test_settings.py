import pytest

from manual_assistant.infrastructure.settings import Settings


def test_reads_cors_origins_as_comma_separated_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_CORS_ORIGINS", "http://servidor, http://servidor:8080 ,")

    settings = Settings(_env_file=None)

    assert settings.cors_origins == ["http://servidor", "http://servidor:8080"]


def test_uses_development_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_ENVIRONMENT", raising=False)
    monkeypatch.delenv("APP_CORS_ORIGINS", raising=False)

    settings = Settings(_env_file=None)

    assert settings.environment == "development"
    assert settings.cors_origins == ["http://localhost:5173"]
