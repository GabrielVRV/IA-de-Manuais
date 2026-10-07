from manual_assistant.application.errors import ManualNotFoundError
from manual_assistant.application.ports.file_storage import FileStorage
from manual_assistant.application.ports.manual_repository import ManualRepository
from manual_assistant.application.ports.vector_store import VectorStore
from manual_assistant.application.use_cases.manual_files import original_file_key
from manual_assistant.domain.manual import ManualId


class DeleteManualUseCase:
    """Remove o manual, seus trechos indexados e o arquivo original."""

    def __init__(
        self,
        *,
        repository: ManualRepository,
        vector_store: VectorStore,
        storage: FileStorage,
    ) -> None:
        self._repository = repository
        self._vector_store = vector_store
        self._storage = storage

    async def execute(self, manual_id: ManualId) -> None:
        if await self._repository.get(manual_id) is None:
            raise ManualNotFoundError(manual_id)

        # Trechos primeiro: o manual deixa de aparecer nas respostas imediatamente.
        await self._vector_store.delete_by_manual(manual_id)
        await self._repository.delete(manual_id)
        await self._storage.delete(original_file_key(manual_id))
