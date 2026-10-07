"""Testa o adaptador do Gemini interceptando o HTTP do SDK (sem rede e sem gastar cota)."""

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from manual_assistant.application.errors import ExternalServiceError
from manual_assistant.application.ports.language_model import CompletionRequest
from manual_assistant.infrastructure.ai.gemini_provider import (
    GeminiEmbeddingProvider,
    GeminiLanguageModel,
    create_gemini_client,
)

pytestmark = pytest.mark.anyio

DIMENSIONS = 4
Handler = Callable[[httpx.Request], httpx.Response]


class FakeGeminiApi:
    def __init__(self) -> None:
        self.requests: list[tuple[str, dict[str, Any]]] = []
        self.failure: httpx.Response | Exception | None = None
        self.generation: dict[str, Any] = {
            "candidates": [
                {
                    "content": {"role": "model", "parts": [{"text": "180 bar."}]},
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 4,
                "thoughtsTokenCount": 3,
            },
            "modelVersion": "gemini-3.5-flash-001",
        }

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.requests.append((request.url.path, body))
        if isinstance(self.failure, Exception):
            raise self.failure
        if self.failure is not None:
            return self.failure
        if request.url.path.endswith(":batchEmbedContents"):
            count = len(body["requests"])
            return httpx.Response(
                200,
                json={"embeddings": [{"values": [float(i)] * DIMENSIONS} for i in range(count)]},
            )
        return httpx.Response(200, json=self.generation)

    def client(self) -> Any:
        return create_gemini_client(
            "chave-falsa",
            attempts=1,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(self)),
        )


@pytest.fixture
def api() -> FakeGeminiApi:
    return FakeGeminiApi()


@pytest.fixture
def embeddings(api: FakeGeminiApi) -> GeminiEmbeddingProvider:
    return GeminiEmbeddingProvider(
        api.client(), model="gemini-embedding-001", dimensions=DIMENSIONS
    )


class TestEmbeddings:
    async def test_embeds_documents_in_batches_of_100(
        self, api: FakeGeminiApi, embeddings: GeminiEmbeddingProvider
    ) -> None:
        vectors = await embeddings.embed_documents([f"trecho {i}" for i in range(150)])

        assert len(vectors) == 150
        assert [len(body["requests"]) for _, body in api.requests] == [100, 50]
        first = api.requests[0][1]["requests"][0]
        assert first["taskType"] == "RETRIEVAL_DOCUMENT"
        assert first["outputDimensionality"] == DIMENSIONS
        assert api.requests[0][0].endswith("models/gemini-embedding-001:batchEmbedContents")

    async def test_embeds_queries_with_the_query_task_type(
        self, api: FakeGeminiApi, embeddings: GeminiEmbeddingProvider
    ) -> None:
        vector = await embeddings.embed_query("qual a pressão?")

        assert len(vector) == DIMENSIONS
        assert api.requests[0][1]["requests"][0]["taskType"] == "RETRIEVAL_QUERY"

    async def test_rejects_vectors_with_unexpected_dimensions(self, api: FakeGeminiApi) -> None:
        provider = GeminiEmbeddingProvider(api.client(), model="m", dimensions=DIMENSIONS + 1)

        with pytest.raises(ExternalServiceError, match="dimensões"):
            await provider.embed_query("x")


@pytest.mark.parametrize(
    ("failure", "message"),
    [
        (httpx.Response(401, json={"error": {"code": 401, "message": "bad key"}}), "chave de API"),
        (httpx.Response(429, json={"error": {"code": 429, "message": "quota"}}), "Cota"),
        (httpx.Response(500, json={"error": {"code": 500, "message": "boom"}}), "HTTP 500"),
        (
            httpx.Response(400, json={"error": {"code": 400, "message": "invalid argument"}}),
            r"HTTP 400\): invalid argument",
        ),
        (httpx.ConnectError("sem rede"), "Sem resposta"),
    ],
    ids=["chave-invalida", "cota", "erro-servidor", "requisicao-invalida", "sem-rede"],
)
async def test_translates_failures(
    api: FakeGeminiApi,
    embeddings: GeminiEmbeddingProvider,
    failure: httpx.Response | Exception,
    message: str,
) -> None:
    api.failure = failure

    with pytest.raises(ExternalServiceError, match=message):
        await embeddings.embed_query("x")


class TestLanguageModel:
    REQUEST = CompletionRequest(
        system_instruction="Responda com base nos manuais.",
        prompt="Qual a pressão máxima?",
        temperature=0.2,
        max_output_tokens=512,
    )

    async def test_sends_the_request_without_thinking(self, api: FakeGeminiApi) -> None:
        model = GeminiLanguageModel(api.client(), model="gemini-3.5-flash")

        await model.complete(self.REQUEST)

        path, body = api.requests[0]
        assert path.endswith("models/gemini-3.5-flash:generateContent")
        assert body["systemInstruction"]["parts"][0]["text"] == "Responda com base nos manuais."
        assert body["contents"][0]["parts"][0]["text"] == "Qual a pressão máxima?"
        config = body["generationConfig"]
        assert config["temperature"] == 0.2
        assert config["maxOutputTokens"] == 512
        assert config["thinkingConfig"]["thinking_budget"] == 0

    async def test_omits_thinking_config_when_budget_is_none(self, api: FakeGeminiApi) -> None:
        model = GeminiLanguageModel(
            api.client(), model="gemini-3.5-flash-lite", thinking_budget=None
        )

        await model.complete(self.REQUEST)

        assert "thinkingConfig" not in api.requests[0][1]["generationConfig"]

    async def test_maps_text_model_and_billed_tokens(self, api: FakeGeminiApi) -> None:
        completion = await GeminiLanguageModel(api.client(), model="m").complete(self.REQUEST)

        assert completion.text == "180 bar."
        assert completion.model == "gemini-3.5-flash-001"
        assert completion.usage.input_tokens == 10
        assert completion.usage.output_tokens == 7  # resposta + raciocínio, ambos cobrados

    async def test_fails_when_no_text_is_returned(self, api: FakeGeminiApi) -> None:
        api.generation = {"candidates": [{"finishReason": "SAFETY"}]}

        with pytest.raises(ExternalServiceError, match="SAFETY"):
            await GeminiLanguageModel(api.client(), model="m").complete(self.REQUEST)
