"""Fluxo completo com banco real, PDF real e armazenamento real; só a IA é falsa."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from manual_assistant.application.use_cases.recover_interrupted_indexing import (
    INTERRUPTED_REASON,
)
from manual_assistant.infrastructure.ai.factory import AiProviders
from manual_assistant.infrastructure.persistence.manual_repository import (
    SqlAlchemyManualRepository,
)
from manual_assistant.infrastructure.persistence.models import EMBEDDING_DIMENSIONS
from manual_assistant.infrastructure.persistence.vector_store import PgVectorStore
from manual_assistant.infrastructure.settings import Settings
from manual_assistant.main import create_app
from tests.factories import make_manual
from tests.fakes import FakeEmbeddingProvider, FakeLanguageModel
from tests.pdf_builder import build_pdf

# Fixtures do banco são assíncronas: todos os testes do módulo rodam com anyio.
pytestmark = [pytest.mark.db, pytest.mark.anyio]

URL = "/api/v1/manuals"


@pytest.fixture
def settings(postgres_settings: Settings, tmp_path: Path) -> Settings:
    return postgres_settings.model_copy(update={"storage_dir": tmp_path / "manuais"})


@pytest.fixture
def client(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],  # noqa: ARG001 - limpa o banco ao final
) -> Iterator[TestClient]:
    ai = AiProviders(
        embeddings=FakeEmbeddingProvider(dimensions=EMBEDDING_DIMENSIONS),
        language_model=FakeLanguageModel(),
    )
    with TestClient(create_app(settings, ai_providers=ai)) as client:
        yield client


async def test_uploaded_manual_is_indexed_and_searchable(
    client: TestClient, settings: Settings, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    pdf = build_pdf("Manual da Prensa P-200\nPressão máxima: 180 bar", "Troca de óleo")
    files = {"file": ("prensa.pdf", pdf, "application/pdf")}

    manual_id = client.post(URL, files=files, data={"title": "Prensa P-200"}).json()["id"]

    manual = client.get(f"{URL}/{manual_id}").json()
    assert (manual["status"], manual["page_count"]) == ("indexed", 2)
    assert (settings.storage_dir / f"{manual_id}.pdf").read_bytes() == pdf

    store = PgVectorStore(session_factory)
    query = await FakeEmbeddingProvider(dimensions=EMBEDDING_DIMENSIONS).embed_query("pressão")
    results = await store.search(query, limit=5)
    assert results[0].chunk.manual_title == "Prensa P-200"
    assert "180 bar" in results[0].chunk.text


async def test_answers_questions_citing_the_uploaded_manual(client: TestClient) -> None:
    files = {"file": ("prensa.pdf", build_pdf("Pressão máxima: 180 bar"), "application/pdf")}
    client.post(URL, files=files, data={"title": "Prensa P-200"})

    body = client.post("/api/v1/questions", json={"question": "Qual a pressão?"}).json()

    assert body["found"] is True
    assert body["citations"][0]["manual_title"] == "Prensa P-200"
    assert body["citations"][0]["pages_label"] == "p. 1"


async def test_deleting_removes_everything(client: TestClient, settings: Settings) -> None:
    files = {"file": ("m.pdf", build_pdf("Conteúdo"), "application/pdf")}
    manual_id = client.post(URL, files=files).json()["id"]

    assert client.delete(f"{URL}/{manual_id}").status_code == 204
    assert client.get(URL).json() == []
    assert not (settings.storage_dir / f"{manual_id}.pdf").exists()


async def test_startup_fails_indexing_interrupted_by_a_restart(
    settings: Settings, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    repository = SqlAlchemyManualRepository(session_factory)
    stuck = make_manual()
    stuck.start_processing()
    await repository.save(stuck)
    ai = AiProviders(FakeEmbeddingProvider(dimensions=EMBEDDING_DIMENSIONS), FakeLanguageModel())

    with TestClient(create_app(settings, ai_providers=ai)) as client:
        manual = client.get(f"{URL}/{stuck.id}").json()

    assert manual["status"] == "failed"
    assert manual["failure_reason"] == INTERRUPTED_REASON
