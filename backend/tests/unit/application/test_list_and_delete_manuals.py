from datetime import timedelta
from uuid import uuid4

import pytest

from manual_assistant.application.errors import ManualNotFoundError
from manual_assistant.application.ports.vector_store import EmbeddedChunk
from manual_assistant.application.use_cases.delete_manual import DeleteManualUseCase
from manual_assistant.application.use_cases.list_manuals import ListManualsUseCase
from manual_assistant.application.use_cases.manual_files import original_file_key
from manual_assistant.domain.manual import Manual, ManualId
from tests.factories import FIXED_NOW, make_chunk, make_manual
from tests.fakes import InMemoryFileStorage, InMemoryManualRepository, InMemoryVectorStore

pytestmark = pytest.mark.anyio


async def test_lists_manuals_newest_first() -> None:
    repository = InMemoryManualRepository()
    await repository.save(Manual.register(title="Antigo", file_name="a.pdf", now=FIXED_NOW))
    await repository.save(
        Manual.register(title="Novo", file_name="b.pdf", now=FIXED_NOW + timedelta(hours=1))
    )

    manuals = await ListManualsUseCase(repository).execute()

    assert [m.title for m in manuals] == ["Novo", "Antigo"]


class TestDeleteManual:
    @pytest.fixture
    def repository(self) -> InMemoryManualRepository:
        return InMemoryManualRepository()

    @pytest.fixture
    def vector_store(self) -> InMemoryVectorStore:
        return InMemoryVectorStore()

    @pytest.fixture
    def storage(self) -> InMemoryFileStorage:
        return InMemoryFileStorage()

    @pytest.fixture
    def delete(
        self,
        repository: InMemoryManualRepository,
        vector_store: InMemoryVectorStore,
        storage: InMemoryFileStorage,
    ) -> DeleteManualUseCase:
        return DeleteManualUseCase(
            repository=repository, vector_store=vector_store, storage=storage
        )

    async def test_removes_manual_chunks_and_file(
        self,
        delete: DeleteManualUseCase,
        repository: InMemoryManualRepository,
        vector_store: InMemoryVectorStore,
        storage: InMemoryFileStorage,
    ) -> None:
        manual = make_manual()
        await repository.save(manual)
        await vector_store.upsert([EmbeddedChunk(make_chunk(manual), (1.0, 0.0, 0.0))])
        storage.files[original_file_key(manual.id)] = b"%PDF-"

        await delete.execute(manual.id)

        assert repository.manuals == {}
        assert vector_store.items == {}
        assert storage.files == {}

    async def test_rejects_unknown_manual(self, delete: DeleteManualUseCase) -> None:
        with pytest.raises(ManualNotFoundError):
            await delete.execute(ManualId(uuid4()))
