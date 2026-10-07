import pytest

from manual_assistant.infrastructure.ai.factory import AiConfigurationError, build_ai_providers
from manual_assistant.infrastructure.ai.gemini_provider import (
    GeminiEmbeddingProvider,
    GeminiLanguageModel,
)
from manual_assistant.infrastructure.ai.openai_provider import (
    OpenAIEmbeddingProvider,
    OpenAILanguageModel,
)
from manual_assistant.infrastructure.settings import Settings


def settings(**values: object) -> Settings:
    return Settings(_env_file=None, db_password="x", **values)  # type: ignore[arg-type]


def test_builds_gemini_providers() -> None:
    ai = build_ai_providers(
        settings(ai_provider="gemini", gemini_api_key="k"), embedding_dimensions=1536
    )

    assert isinstance(ai.embeddings, GeminiEmbeddingProvider)
    assert isinstance(ai.language_model, GeminiLanguageModel)
    assert ai.embeddings.dimensions == 1536


def test_builds_openai_providers() -> None:
    ai = build_ai_providers(
        settings(ai_provider="openai", openai_api_key="k"), embedding_dimensions=1536
    )

    assert isinstance(ai.embeddings, OpenAIEmbeddingProvider)
    assert isinstance(ai.language_model, OpenAILanguageModel)


@pytest.mark.parametrize(
    ("provider", "variable"),
    [("gemini", "APP_GEMINI_API_KEY"), ("openai", "APP_OPENAI_API_KEY")],
)
def test_refuses_to_start_without_the_api_key(provider: str, variable: str) -> None:
    with pytest.raises(AiConfigurationError, match=variable):
        build_ai_providers(settings(ai_provider=provider), embedding_dimensions=1536)
