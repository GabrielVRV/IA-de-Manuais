from collections.abc import Callable
from datetime import UTC, datetime

from manual_assistant.application.errors import InvalidDocumentError
from manual_assistant.application.ports.file_storage import FileStorage
from manual_assistant.application.ports.manual_repository import ManualRepository
from manual_assistant.application.use_cases.manual_files import original_file_key
from manual_assistant.domain.manual import Manual

PDF_SIGNATURE = b"%PDF-"
DEFAULT_MAX_BYTES = 50 * 1024 * 1024


def _utc_now() -> datetime:
    return datetime.now(UTC)


class RegisterManualUseCase:
    """Recebe o PDF de um manual e o cadastra como pendente de indexação."""

    def __init__(
        self,
        repository: ManualRepository,
        storage: FileStorage,
        *,
        max_bytes: int = DEFAULT_MAX_BYTES,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._max_bytes = max_bytes
        self._clock = clock

    async def execute(self, *, title: str, file_name: str, content: bytes) -> Manual:
        self._validate(content)
        manual = Manual.register(title=title, file_name=file_name, now=self._clock())

        key = original_file_key(manual.id)
        await self._storage.save(key, content)
        try:
            await self._repository.save(manual)
        except Exception:
            # Sem o cadastro, o arquivo ficaria órfão no armazenamento.
            await self._storage.delete(key)
            raise
        return manual

    def _validate(self, content: bytes) -> None:
        if not content:
            raise InvalidDocumentError("O arquivo enviado está vazio")
        if len(content) > self._max_bytes:
            limit_mb = self._max_bytes // (1024 * 1024)
            raise InvalidDocumentError(f"O arquivo excede o limite de {limit_mb} MB")
        # Confere o conteúdo, não a extensão: um .pdf renomeado não passa.
        if not content.startswith(PDF_SIGNATURE):
            raise InvalidDocumentError("O arquivo enviado não é um PDF")
