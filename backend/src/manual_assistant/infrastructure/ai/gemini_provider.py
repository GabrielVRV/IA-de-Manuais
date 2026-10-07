"""Adaptadores do Google Gemini (API para desenvolvedores, SDK ``google-genai``)."""

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager

import httpx
from google import genai
from google.genai import errors, types

from manual_assistant.application.errors import ExternalServiceError
from manual_assistant.application.ports.embedding_provider import Embedding
from manual_assistant.application.ports.language_model import (
    Completion,
    CompletionRequest,
    TokenUsage,
)
from manual_assistant.infrastructure.ai.batching import batched

# Limite de textos por chamada de batchEmbedContents.
EMBEDDING_BATCH_SIZE = 100


def create_gemini_client(
    api_key: str,
    *,
    timeout_seconds: float = 60,
    attempts: int = 4,
    http_client: httpx.AsyncClient | None = None,
) -> genai.Client:
    """Cliente com repetição automática: o Gemini devolve 503/429 em picos de demanda."""
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=int(timeout_seconds * 1000),
            retry_options=types.HttpRetryOptions(
                attempts=attempts, initial_delay=1.0, max_delay=16.0
            ),
            httpx_async_client=http_client,
        ),
    )


@asynccontextmanager
async def _translate_errors(operation: str) -> AsyncIterator[None]:
    try:
        yield
    except errors.APIError as error:
        raise ExternalServiceError(_describe(error, operation)) from error
    except (TimeoutError, httpx.HTTPError, OSError) as error:
        raise ExternalServiceError(f"Sem resposta do Gemini ao {operation}") from error


def _describe(error: errors.APIError, operation: str) -> str:
    if error.code in (401, 403):
        return f"Gemini recusou a chave de API ao {operation} (verifique APP_GEMINI_API_KEY)"
    if error.code == 429:
        return f"Cota do Gemini excedida ao {operation}"
    return f"Gemini falhou ao {operation} (HTTP {error.code})"


class GeminiEmbeddingProvider:
    """Embeddings do Gemini.

    Usa o ``gemini-embedding-001`` por padrão: o ``gemini-embedding-2`` é multimodal e
    combina todos os textos de uma chamada num único vetor, o que impede o envio em lote.
    """

    def __init__(self, client: genai.Client, *, model: str, dimensions: int) -> None:
        self._client = client
        self._model = model
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed_documents(self, texts: Sequence[str]) -> Sequence[Embedding]:
        vectors: list[Embedding] = []
        for batch in batched(texts, EMBEDDING_BATCH_SIZE):
            vectors.extend(await self._embed(batch, task_type="RETRIEVAL_DOCUMENT"))
        return vectors

    async def embed_query(self, text: str) -> Embedding:
        (vector,) = await self._embed([text], task_type="RETRIEVAL_QUERY")
        return vector

    async def _embed(self, texts: Sequence[str], *, task_type: str) -> list[Embedding]:
        async with _translate_errors("gerar embeddings"):
            response = await self._client.aio.models.embed_content(
                model=self._model,
                contents=list(texts),
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=self._dimensions,
                ),
            )
        vectors = [tuple(e.values or ()) for e in response.embeddings or []]
        if len(vectors) != len(texts) or any(len(v) != self._dimensions for v in vectors):
            raise ExternalServiceError(
                f"Gemini retornou embeddings inesperados para {len(texts)} textos "
                f"(esperado: {self._dimensions} dimensões cada)"
            )
        return vectors


class GeminiLanguageModel:
    def __init__(self, client: genai.Client, *, model: str, thinking_budget: int = 0) -> None:
        self._client = client
        self._model = model
        # 0 desliga o "raciocínio": responder a partir de trechos não precisa dele, e os
        # tokens de raciocínio são cobrados e consomem o limite de saída.
        self._thinking_budget = thinking_budget

    async def complete(self, request: CompletionRequest) -> Completion:
        async with _translate_errors("gerar a resposta"):
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=request.prompt,
                config=types.GenerateContentConfig(
                    system_instruction=request.system_instruction,
                    temperature=request.temperature,
                    max_output_tokens=request.max_output_tokens,
                    thinking_config=types.ThinkingConfig(thinking_budget=self._thinking_budget),
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                ),
            )

        text = response.text
        if not text:
            reason = response.candidates[0].finish_reason if response.candidates else None
            raise ExternalServiceError(f"Gemini não retornou texto (motivo: {reason})")

        usage = response.usage_metadata
        input_tokens = (usage.prompt_token_count or 0) if usage else 0
        # Tokens de raciocínio são cobrados como saída.
        output_tokens = (
            (usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0) if usage else 0
        )
        return Completion(
            text=text,
            model=response.model_version or self._model,
            usage=TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens),
        )
