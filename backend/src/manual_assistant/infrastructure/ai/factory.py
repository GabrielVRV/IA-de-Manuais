from dataclasses import dataclass

from manual_assistant.application.ports.embedding_provider import EmbeddingProvider
from manual_assistant.application.ports.language_model import LanguageModel
from manual_assistant.infrastructure.ai.gemini_provider import (
    GeminiEmbeddingProvider,
    GeminiLanguageModel,
    create_gemini_client,
)
from manual_assistant.infrastructure.ai.openai_provider import (
    OpenAIEmbeddingProvider,
    OpenAILanguageModel,
    create_openai_client,
)
from manual_assistant.infrastructure.settings import Settings


class AiConfigurationError(ValueError):
    """Configuração do provedor de IA incompleta: a API não deve nem iniciar."""


@dataclass(frozen=True, slots=True)
class AiProviders:
    embeddings: EmbeddingProvider
    language_model: LanguageModel


def build_ai_providers(settings: Settings, *, embedding_dimensions: int) -> AiProviders:
    """Escolhe o provedor pelo APP_AI_PROVIDER. Trocar de provedor não altera nenhum caso de uso."""
    if settings.ai_provider == "gemini":
        if settings.gemini_api_key is None:
            raise AiConfigurationError("APP_AI_PROVIDER=gemini exige APP_GEMINI_API_KEY")
        gemini = create_gemini_client(
            settings.gemini_api_key.get_secret_value(),
            timeout_seconds=settings.ai_timeout_seconds,
            attempts=settings.ai_attempts,
        )
        return AiProviders(
            embeddings=GeminiEmbeddingProvider(
                gemini, model=settings.gemini_embedding_model, dimensions=embedding_dimensions
            ),
            language_model=GeminiLanguageModel(
                gemini,
                model=settings.gemini_chat_model,
                thinking_budget=settings.gemini_thinking_budget,
            ),
        )

    if settings.openai_api_key is None:
        raise AiConfigurationError("APP_AI_PROVIDER=openai exige APP_OPENAI_API_KEY")
    client = create_openai_client(
        settings.openai_api_key.get_secret_value(),
        timeout_seconds=settings.ai_timeout_seconds,
        attempts=settings.ai_attempts,
    )
    return AiProviders(
        embeddings=OpenAIEmbeddingProvider(
            client, model=settings.openai_embedding_model, dimensions=embedding_dimensions
        ),
        language_model=OpenAILanguageModel(client, model=settings.openai_chat_model),
    )
