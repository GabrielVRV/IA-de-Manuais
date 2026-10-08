"""Adaptadores do Google Gemini (API para desenvolvedores, SDK ``google-genai``)."""

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
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

logger = logging.getLogger(__name__)

# Limite de textos por chamada de batchEmbedContents.
EMBEDDING_BATCH_SIZE = 100
# Esperas seguidas pela cota num mesmo lote antes de desistir (ex.: cota diária esgotada).
MAX_QUOTA_WAITS_PER_BATCH = 5


class _QuotaExceededError(ExternalServiceError):
    """429 do Gemini: a cota (por minuto ou por dia) foi esgotada."""


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
        if error.code == 429:
            raise _QuotaExceededError(_describe(error, operation)) from error
        raise ExternalServiceError(_describe(error, operation)) from error
    except (TimeoutError, httpx.HTTPError, OSError) as error:
        raise ExternalServiceError(f"Sem resposta do Gemini ao {operation}") from error


def _describe(error: errors.APIError, operation: str) -> str:
    if error.code in (401, 403):
        return f"Gemini recusou a chave de API ao {operation} (verifique APP_GEMINI_API_KEY)"
    if error.code == 429:
        return f"Cota do Gemini excedida ao {operation}"
    # O motivo informado pelo Google revela erros de configuração (ex.: parâmetro não
    # suportado pelo modelo) sem expor a chave.
    detail = f": {error.message[:200]}" if error.message else ""
    return f"Gemini falhou ao {operation} (HTTP {error.code}){detail}"


class GeminiEmbeddingProvider:
    """Embeddings do Gemini.

    Usa o ``gemini-embedding-001`` por padrão: o ``gemini-embedding-2`` é multimodal e
    combina todos os textos de uma chamada num único vetor, o que impede o envio em lote.

    Para o plano gratuito (cota de ~100 textos e ~30 mil tokens por minuto), use lotes
    menores e ``quota_wait_seconds`` > 0: ao receber 429, espera a cota liberar e repete o
    lote, em vez de falhar o manual inteiro.
    """

    def __init__(
        self,
        client: genai.Client,
        *,
        model: str,
        dimensions: int,
        batch_size: int = EMBEDDING_BATCH_SIZE,
        quota_wait_seconds: float = 0,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._client = client
        self._model = model
        self._dimensions = dimensions
        self._batch_size = batch_size
        self._quota_wait_seconds = quota_wait_seconds
        self._sleep = sleep
        # Um manual por vez: indexações simultâneas disputariam a mesma cota.
        self._documents_lock = asyncio.Lock()

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed_documents(self, texts: Sequence[str]) -> Sequence[Embedding]:
        vectors: list[Embedding] = []
        async with self._documents_lock:
            for batch in batched(texts, self._batch_size):
                vectors.extend(await self._embed_waiting_for_quota(batch))
        return vectors

    async def _embed_waiting_for_quota(self, batch: Sequence[str]) -> list[Embedding]:
        waits = 0
        while True:
            try:
                return await self._embed(batch, task_type="RETRIEVAL_DOCUMENT")
            except _QuotaExceededError:
                if self._quota_wait_seconds <= 0 or waits >= MAX_QUOTA_WAITS_PER_BATCH:
                    raise
                waits += 1
                logger.warning(
                    "Cota do Gemini excedida; aguardando %.0f s (tentativa %d de %d)",
                    self._quota_wait_seconds,
                    waits,
                    MAX_QUOTA_WAITS_PER_BATCH,
                )
                await self._sleep(self._quota_wait_seconds)

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
    def __init__(
        self, client: genai.Client, *, model: str, thinking_budget: int | None = 0
    ) -> None:
        self._client = client
        self._model = model
        # 0 desliga o "raciocínio": responder a partir de trechos não precisa dele, e os
        # tokens de raciocínio são cobrados e consomem o limite de saída.
        # None não envia a configuração: modelos sem raciocínio (ex.: flash-lite) recusam
        # qualquer thinking_budget com "invalid argument".
        self._thinking_config = (
            None
            if thinking_budget is None
            else types.ThinkingConfig(thinking_budget=thinking_budget)
        )

    async def complete(self, request: CompletionRequest) -> Completion:
        async with _translate_errors("gerar a resposta"):
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=request.prompt,
                config=types.GenerateContentConfig(
                    system_instruction=request.system_instruction,
                    temperature=request.temperature,
                    max_output_tokens=request.max_output_tokens,
                    thinking_config=self._thinking_config,
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
