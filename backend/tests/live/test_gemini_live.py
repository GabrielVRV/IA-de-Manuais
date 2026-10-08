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
from manual_assistant.application.rag_prompt import NOT_FOUND_MESSAGE
from manual_assistant.application.use_cases.ask_question import AskQuestionUseCase
from manual_assistant.domain.chunk import ScoredChunk
from manual_assistant.domain.pages import PageRange
from manual_assistant.domain.question import Question
from manual_assistant.infrastructure.ai.gemini_provider import (
    GeminiEmbeddingProvider,
    GeminiLanguageModel,
    create_gemini_client,
)
from manual_assistant.infrastructure.persistence.models import EMBEDDING_DIMENSIONS
from manual_assistant.infrastructure.settings import Settings
from tests.factories import make_chunk, make_manual
from tests.fakes import FakeEmbeddingProvider, InMemoryVectorStore

settings = Settings(db_password="nao-usado", auth_secret_key="x" * 32)  # lê o .env, se existir
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


def ask_question_use_case(client: genai.Client) -> AskQuestionUseCase:
    """Busca fixa (dois trechos de manuais diferentes); só o modelo de linguagem é real."""
    prensa, torno = make_manual("Manual da Prensa P-200"), make_manual("Manual do Torno T-10")
    results = [
        ScoredChunk(
            make_chunk(
                torno,
                text="Rotação máxima do eixo: 3000 rpm. Use óculos de proteção.",
                pages=PageRange.single(4),
            ),
            0.7,
        ),
        ScoredChunk(
            make_chunk(
                prensa,
                text="Pressão máxima de trabalho: 180 bar. Não exceda este valor.",
                pages=PageRange(12, 13),
            ),
            0.6,
        ),
    ]
    return AskQuestionUseCase(
        embeddings=FakeEmbeddingProvider(),
        vector_store=InMemoryVectorStore(search_results=results),
        language_model=GeminiLanguageModel(
            client,
            model=settings.gemini_chat_model,
            thinking_budget=settings.gemini_thinking_budget,
        ),
    )


async def test_model_answers_from_the_chunks_and_cites_the_right_source(
    client: genai.Client,
) -> None:
    answer = await ask_question_use_case(client).execute(
        Question("Qual a pressão máxima da prensa P-200?")
    )

    assert "180" in answer.text
    assert [c.manual_title for c in answer.citations] == ["Manual da Prensa P-200"]


async def test_model_says_it_did_not_find_unrelated_information(client: genai.Client) -> None:
    answer = await ask_question_use_case(client).execute(Question("Como faço um bolo de cenoura?"))

    assert answer.text == NOT_FOUND_MESSAGE
    assert not answer.has_sources
