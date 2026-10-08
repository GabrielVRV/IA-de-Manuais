"""Monta a API HTTP com fakes em memória (sem banco nem IA reais)."""

from dataclasses import dataclass, field

from fastapi import FastAPI

from manual_assistant import __version__
from manual_assistant.application.ports.health_indicator import HealthIndicator
from manual_assistant.application.use_cases.ask_question import AskQuestionUseCase
from manual_assistant.application.use_cases.check_health import CheckHealthUseCase
from manual_assistant.application.use_cases.delete_manual import DeleteManualUseCase
from manual_assistant.application.use_cases.get_manual import GetManualUseCase
from manual_assistant.application.use_cases.get_manual_file import GetManualFileUseCase
from manual_assistant.application.use_cases.index_manual import IndexManualUseCase
from manual_assistant.application.use_cases.list_manuals import ListManualsUseCase
from manual_assistant.application.use_cases.register_manual import RegisterManualUseCase
from manual_assistant.infrastructure.documents.line_chunker import LineChunker
from manual_assistant.infrastructure.documents.pdf_parser import PdfiumDocumentParser
from manual_assistant.presentation.http.app import create_http_app
from manual_assistant.presentation.http.dependencies import UseCases
from tests.fakes import (
    FakeEmbeddingProvider,
    FakeLanguageModel,
    InMemoryFileStorage,
    InMemoryManualRepository,
    InMemoryVectorStore,
)

FRONTEND_ORIGIN = "http://servidor-interno"


@dataclass
class FakeBackend:
    """Dependências em memória, expostas para os testes inspecionarem o resultado."""

    repository: InMemoryManualRepository = field(default_factory=InMemoryManualRepository)
    storage: InMemoryFileStorage = field(default_factory=InMemoryFileStorage)
    embeddings: FakeEmbeddingProvider = field(default_factory=FakeEmbeddingProvider)
    vector_store: InMemoryVectorStore = field(default_factory=InMemoryVectorStore)
    language_model: FakeLanguageModel = field(default_factory=FakeLanguageModel)
    health_indicators: list[HealthIndicator] = field(default_factory=list)
    max_upload_bytes: int = 1024 * 1024

    def build_app(self) -> FastAPI:
        use_cases = UseCases(
            check_health=CheckHealthUseCase(self.health_indicators),
            register_manual=RegisterManualUseCase(
                self.repository, self.storage, max_bytes=self.max_upload_bytes
            ),
            index_manual=IndexManualUseCase(
                repository=self.repository,
                storage=self.storage,
                parser=PdfiumDocumentParser(),  # real: os PDFs dos testes são gerados
                chunker=LineChunker(),
                embeddings=self.embeddings,
                vector_store=self.vector_store,
            ),
            list_manuals=ListManualsUseCase(self.repository),
            get_manual=GetManualUseCase(self.repository),
            get_manual_file=GetManualFileUseCase(self.repository, self.storage),
            delete_manual=DeleteManualUseCase(
                repository=self.repository, vector_store=self.vector_store, storage=self.storage
            ),
            ask_question=AskQuestionUseCase(
                embeddings=self.embeddings,
                vector_store=self.vector_store,
                language_model=self.language_model,
            ),
        )
        return create_http_app(
            title="test",
            version=__version__,
            cors_origins=[FRONTEND_ORIGIN],
            use_cases=use_cases,
        )
