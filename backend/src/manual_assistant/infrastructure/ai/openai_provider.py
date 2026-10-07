"""Adaptadores da OpenAI (SDK ``openai``)."""

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager

import httpx2
import openai
from openai import AsyncOpenAI, omit

from manual_assistant.application.errors import ExternalServiceError
from manual_assistant.application.ports.embedding_provider import Embedding
from manual_assistant.application.ports.language_model import (
    Completion,
    CompletionRequest,
    TokenUsage,
)
from manual_assistant.infrastructure.ai.batching import batched

EMBEDDING_BATCH_SIZE = 512

# Modelos de raciocínio (o1, o3, gpt-5...) não aceitam o parâmetro temperature.
_REASONING_MODEL_PREFIXES = ("o1", "o3", "o4", "gpt-5")


def create_openai_client(
    api_key: str,
    *,
    timeout_seconds: float = 60,
    attempts: int = 4,
    http_client: httpx2.AsyncClient | None = None,  # o SDK 3.x usa httpx2
    base_url: str | None = None,
) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=api_key,
        timeout=timeout_seconds,
        max_retries=attempts - 1,  # o SDK repete sozinho em 429 e 5xx
        http_client=http_client,
        base_url=base_url,
    )


@asynccontextmanager
async def _translate_errors(operation: str) -> AsyncIterator[None]:
    try:
        yield
    except openai.AuthenticationError as error:
        raise ExternalServiceError(
            f"OpenAI recusou a chave de API ao {operation} (verifique APP_OPENAI_API_KEY)"
        ) from error
    except openai.RateLimitError as error:
        raise ExternalServiceError(f"Cota da OpenAI excedida ao {operation}") from error
    except openai.APIStatusError as error:
        raise ExternalServiceError(
            f"OpenAI falhou ao {operation} (HTTP {error.status_code})"
        ) from error
    except openai.APIError as error:  # conexão, timeout
        raise ExternalServiceError(f"Sem resposta da OpenAI ao {operation}") from error


class OpenAIEmbeddingProvider:
    def __init__(self, client: AsyncOpenAI, *, model: str, dimensions: int) -> None:
        self._client = client
        self._model = model
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed_documents(self, texts: Sequence[str]) -> Sequence[Embedding]:
        vectors: list[Embedding] = []
        for batch in batched(texts, EMBEDDING_BATCH_SIZE):
            vectors.extend(await self._embed(batch))
        return vectors

    async def embed_query(self, text: str) -> Embedding:
        (vector,) = await self._embed([text])
        return vector

    async def _embed(self, texts: Sequence[str]) -> list[Embedding]:
        async with _translate_errors("gerar embeddings"):
            response = await self._client.embeddings.create(
                model=self._model,
                input=list(texts),
                dimensions=self._dimensions,
            )
        ordered = sorted(response.data, key=lambda item: item.index)
        vectors = [tuple(item.embedding) for item in ordered]
        if len(vectors) != len(texts) or any(len(v) != self._dimensions for v in vectors):
            raise ExternalServiceError(
                f"OpenAI retornou embeddings inesperados para {len(texts)} textos "
                f"(esperado: {self._dimensions} dimensões cada)"
            )
        return vectors


class OpenAILanguageModel:
    def __init__(self, client: AsyncOpenAI, *, model: str) -> None:
        self._client = client
        self._model = model

    async def complete(self, request: CompletionRequest) -> Completion:
        # Modelos de raciocínio recusam temperature: nesses casos o parâmetro é omitido.
        temperature = (
            omit if self._model.startswith(_REASONING_MODEL_PREFIXES) else request.temperature
        )
        async with _translate_errors("gerar a resposta"):
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": request.system_instruction},
                    {"role": "user", "content": request.prompt},
                ],
                max_completion_tokens=request.max_output_tokens,
                temperature=temperature,
            )

        choice = response.choices[0] if response.choices else None
        text = choice.message.content if choice else None
        if not text:
            reason = choice.finish_reason if choice else None
            raise ExternalServiceError(f"OpenAI não retornou texto (motivo: {reason})")

        usage = response.usage
        return Completion(
            text=text,
            model=response.model,
            usage=TokenUsage(
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
            ),
        )
