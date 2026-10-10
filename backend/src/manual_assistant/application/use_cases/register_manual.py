from manual_assistant.application.clock import Clock, utc_now
from manual_assistant.application.errors import InvalidDocumentError
from manual_assistant.application.ports.file_storage import FileStorage
from manual_assistant.application.ports.manual_repository import ManualRepository
from manual_assistant.application.use_cases.manual_files import original_file_key
from manual_assistant.domain.manual import Manual, SourceFile

PDF_SIGNATURE = b"%PDF-"
DEFAULT_MAX_BYTES = 50 * 1024 * 1024


class RegisterManualUseCase:
    """Recebe o PDF de um manual e o cadastra como pendente de indexação."""

    def __init__(
        self,
        repository: ManualRepository,
        storage: FileStorage,
        *,
        max_bytes: int = DEFAULT_MAX_BYTES,
        clock: Clock = utc_now,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._max_bytes = max_bytes
        self._clock = clock

    @property
    def max_bytes(self) -> int:
        return self._max_bytes

    async def execute(
        self, *, title: str, file_name: str, content: bytes, source: SourceFile | None = None
    ) -> Manual:
        """``source``: preenchido quando o manual vem da pasta da Engenharia."""
        validate_pdf(content, max_bytes=self._max_bytes)
        manual = Manual.register(title=title, file_name=file_name, now=self._clock(), source=source)

        key = original_file_key(manual.id)
        await self._storage.save(key, content)
        try:
            await self._repository.save(manual)
        except Exception:
            # Sem o cadastro, o arquivo ficaria órfão no armazenamento.
            await self._storage.delete(key)
            raise
        return manual


def validate_pdf(content: bytes, *, max_bytes: int) -> None:
    """
    Raises:
        InvalidDocumentError: arquivo vazio, grande demais ou que não é PDF.
    """
    if not content:
        raise InvalidDocumentError("O arquivo enviado está vazio")
    if len(content) > max_bytes:
        limit_mb = max_bytes // (1024 * 1024)
        raise InvalidDocumentError(f"O arquivo excede o limite de {limit_mb} MB")
    # Confere o conteúdo, não a extensão: um .pdf renomeado não passa.
    if not content.startswith(PDF_SIGNATURE):
        raise InvalidDocumentError("O arquivo enviado não é um PDF")
