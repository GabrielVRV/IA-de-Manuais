"""Chamadas REAIS ao Gemini: confirmam que o contrato do SDK/API não mudou.

Não rodam por padrão (gastam cota e dependem da internet). Execute com:
    pytest -m live
A chave é lida de APP_GEMINI_API_KEY (variável de ambiente ou backend/.env).
"""

import math

import pytest
from google import genai

from manual_assistant.application.ports.embedding_provider import Embedding
from manual_assistant.application.ports.language_model import CompletionRequest
from manual_assistant.infrastructure.ai.gemini_provider import (
    GeminiEmbeddingProvider,
    GeminiLanguageModel,
    create_gemini_client,
)
from manual_assistant.infrastructure.persistence.models import EMBEDDING_DIMENSIONS
from manual_assistant.infrastructure.settings import Settings

settings = Settings(db_password="nao-usado")  # lê o .env, se existir
api_key = settings.gemini_api_key

pytestmark = [
    pytest.mark.live,
    pytest.mark.anyio,
    pytest.mark.skipif(api_key is None, reason="APP_GEMINI_API_KEY não configurada"),
]


def cosine(a: Embedding, b: Embedding) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return dot / math.sqrt(sum(x * x for x in a) * sum(y * y for y in b))


@pytest.fixture
def client() -> genai.Client:
    assert api_key is not None
    return create_gemini_client(api_key.get_secret_value())


async def test_embeddings_capture_meaning(client: genai.Client) -> None:
    provider = GeminiEmbeddingProvider(
        client,
        model=settings.gemini_embedding_model,
        dimensions=EMBEDDING_DIMENSIONS,
    )

    pressure, oil = await provider.embed_documents(
        ["Pressão máxima de trabalho da prensa: 180 bar.", "Troque o óleo a cada 2000 horas."]
    )
    question = await provider.embed_query("Qual a pressão máxima da prensa?")

    assert len(pressure) == EMBEDDING_DIMENSIONS
    assert cosine(question, pressure) > cosine(question, oil)


async def test_language_model_answers_without_truncation(client: genai.Client) -> None:
    model = GeminiLanguageModel(
        client,
        model=settings.gemini_chat_model,
        thinking_budget=settings.gemini_thinking_budget,
    )

    completion = await model.complete(
        CompletionRequest(
            system_instruction="Responda em português, em uma frase curta.",
            prompt="A pressão máxima é 180 bar. Qual é a pressão máxima?",
            max_output_tokens=200,
        )
    )

    assert "180" in completion.text
    assert completion.usage.input_tokens > 0
    assert completion.usage.output_tokens > 0
