"""Testa o adaptador da OpenAI interceptando o HTTP do SDK (que usa httpx2)."""

import json
from typing import Any

import httpx2
import pytest
from openai import AsyncOpenAI

from manual_assistant.application.errors import ExternalServiceError
from manual_assistant.application.ports.language_model import CompletionRequest
from manual_assistant.infrastructure.ai.openai_provider import (
    OpenAIEmbeddingProvider,
    OpenAILanguageModel,
    create_openai_client,
)

pytestmark = pytest.mark.anyio

DIMENSIONS = 4
REQUEST = CompletionRequest(system_instruction="Sistema", prompt="Pergunta", temperature=0.2)


class FakeOpenAIApi:
    def __init__(self) -> None:
        self.requests: list[tuple[str, dict[str, Any]]] = []
        self.failure: httpx2.Response | Exception | None = None
        self.content: str | None = "180 bar."

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        self.requests.append((request.url.path, body))
        if isinstance(self.failure, Exception):
            raise self.failure
        if self.failure is not None:
            return self.failure
        if request.url.path.endswith("/embeddings"):
            data = [
                {"object": "embedding", "index": i, "embedding": [float(i)] * DIMENSIONS}
                for i in range(len(body["input"]))
            ]
            # Fora de ordem de propósito: o adaptador deve reordenar pelo índice.
            return httpx2.Response(
                200,
                json={
                    "object": "list",
                    "data": list(reversed(data)),
                    "model": body["model"],
                    "usage": {"prompt_tokens": 1, "total_tokens": 1},
                },
            )
        return httpx2.Response(
            200,
            json={
                "id": "chatcmpl-1",
                "object": "chat.completion",
                "created": 0,
                "model": body["model"],
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": self.content},
                        "finish_reason": "stop" if self.content else "content_filter",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            },
        )

    def client(self) -> AsyncOpenAI:
        return create_openai_client(
            "chave-falsa",
            attempts=1,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(self)),
        )


@pytest.fixture
def api() -> FakeOpenAIApi:
    return FakeOpenAIApi()


async def test_embeds_in_order_with_the_configured_dimensions(api: FakeOpenAIApi) -> None:
    provider = OpenAIEmbeddingProvider(api.client(), model="text-embedding-3-small", dimensions=4)

    vectors = await provider.embed_documents(["a", "b", "c"])

    assert [v[0] for v in vectors] == [0.0, 1.0, 2.0]
    assert api.requests[0][1]["dimensions"] == DIMENSIONS


async def test_embeds_a_query(api: FakeOpenAIApi) -> None:
    provider = OpenAIEmbeddingProvider(api.client(), model="m", dimensions=DIMENSIONS)

    assert len(await provider.embed_query("x")) == DIMENSIONS


async def test_completes_with_temperature_for_regular_models(api: FakeOpenAIApi) -> None:
    completion = await OpenAILanguageModel(api.client(), model="gpt-4.1-mini").complete(REQUEST)

    body = api.requests[0][1]
    assert body["temperature"] == 0.2
    assert body["messages"][0] == {"role": "system", "content": "Sistema"}
    assert (completion.text, completion.usage.total_tokens) == ("180 bar.", 15)


async def test_omits_temperature_for_reasoning_models(api: FakeOpenAIApi) -> None:
    await OpenAILanguageModel(api.client(), model="gpt-5.4-mini").complete(REQUEST)

    assert "temperature" not in api.requests[0][1]


async def test_fails_when_no_text_is_returned(api: FakeOpenAIApi) -> None:
    api.content = None

    with pytest.raises(ExternalServiceError, match="content_filter"):
        await OpenAILanguageModel(api.client(), model="m").complete(REQUEST)


@pytest.mark.parametrize(
    ("failure", "message"),
    [
        (httpx2.Response(401, json={"error": {"message": "bad key"}}), "chave de API"),
        (httpx2.Response(429, json={"error": {"message": "quota"}}), "Cota"),
        (httpx2.Response(500, json={"error": {"message": "boom"}}), "HTTP 500"),
        (httpx2.ConnectError("sem rede"), "Sem resposta"),
    ],
    ids=["chave-invalida", "cota", "erro-servidor", "sem-rede"],
)
async def test_translates_failures(
    api: FakeOpenAIApi, failure: httpx2.Response | Exception, message: str
) -> None:
    api.failure = failure

    with pytest.raises(ExternalServiceError, match=message):
        await OpenAILanguageModel(api.client(), model="m").complete(REQUEST)
