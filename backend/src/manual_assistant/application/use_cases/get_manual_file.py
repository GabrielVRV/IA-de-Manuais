from dataclasses import dataclass

from manual_assistant.application.errors import ManualNotFoundError
from manual_assistant.application.ports.assistant_access_repository import (
    AssistantAccessRepository,
)
from manual_assistant.application.ports.file_storage import FileStorage
from manual_assistant.application.ports.manual_repository import ManualRepository
from manual_assistant.application.use_cases.assistant_access import ensure_assistant_access
from manual_assistant.application.use_cases.manual_files import original_file_key
from manual_assistant.domain.assistant import AssistantId
from manual_assistant.domain.manual import ManualId
from manual_assistant.domain.user import User


@dataclass(frozen=True, slots=True)
class ManualFile:
    file_name: str
    content: bytes


class GetManualFileUseCase:
    """Entrega o PDF original, para abrir o manual na página citada.

    Os manuais são do assistente de Engenharia: só quem tem acesso a ele os abre.
    """

    def __init__(
        self,
        repository: ManualRepository,
        storage: FileStorage,
        access: AssistantAccessRepository,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._access = access

    async def execute(self, actor: User, manual_id: ManualId) -> ManualFile:
        """
        Raises:
            AssistantAccessDeniedError: se o usuário não tem acesso ao assistente.
            ManualNotFoundError: se o manual não existir.
            StoredFileNotFoundError: se o arquivo tiver sumido do armazenamento.
        """
        await ensure_assistant_access(self._access, actor, AssistantId.ENGINEERING)
        manual = await self._repository.get(manual_id)
        if manual is None:
            raise ManualNotFoundError(manual_id)
        content = await self._storage.read(original_file_key(manual.id))
        return ManualFile(file_name=manual.file_name, content=content)
