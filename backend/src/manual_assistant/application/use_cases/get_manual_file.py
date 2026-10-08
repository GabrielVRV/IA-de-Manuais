from dataclasses import dataclass

from manual_assistant.application.errors import ManualNotFoundError
from manual_assistant.application.ports.file_storage import FileStorage
from manual_assistant.application.ports.manual_repository import ManualRepository
from manual_assistant.application.use_cases.manual_files import original_file_key
from manual_assistant.domain.manual import ManualId


@dataclass(frozen=True, slots=True)
class ManualFile:
    file_name: str
    content: bytes


class GetManualFileUseCase:
    """Entrega o PDF original, para abrir o manual na página citada."""

    def __init__(self, repository: ManualRepository, storage: FileStorage) -> None:
        self._repository = repository
        self._storage = storage

    async def execute(self, manual_id: ManualId) -> ManualFile:
        """
        Raises:
            ManualNotFoundError: se o manual não existir.
            StoredFileNotFoundError: se o arquivo tiver sumido do armazenamento.
        """
        manual = await self._repository.get(manual_id)
        if manual is None:
            raise ManualNotFoundError(manual_id)
        content = await self._storage.read(original_file_key(manual.id))
        return ManualFile(file_name=manual.file_name, content=content)
