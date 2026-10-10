from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import NewType, Self
from uuid import UUID, uuid4

from manual_assistant.domain.errors import InvalidStateTransitionError, InvalidValueError

ManualId = NewType("ManualId", UUID)

TITLE_MAX_LENGTH = 200


@dataclass(frozen=True, slots=True)
class SourceFile:
    """Arquivo da pasta de manuais da Engenharia de onde o manual foi importado.

    ``key`` identifica o manual entre revisões (código + idioma, ex.: "95007003P");
    ``fingerprint`` (tamanho e data do arquivo) evita reler a pasta a cada sincronização
    e ``content_hash`` (SHA-256) evita reindexar um arquivo que só foi copiado de novo.
    """

    key: str
    fingerprint: str
    content_hash: str

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise InvalidValueError("A chave do arquivo de origem é obrigatória")


class ManualStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


@dataclass(eq=False, kw_only=True, slots=True)
class Manual:
    """Manual de um equipamento e seu ciclo de vida de indexação.

    PENDING ──▶ PROCESSING ──▶ INDEXED
                    │  ▲           │
                    ▼  └───────────┤  (reprocessar)
                  FAILED ──────────┘
    """

    id: ManualId
    title: str
    file_name: str
    created_at: datetime
    status: ManualStatus = ManualStatus.PENDING
    page_count: int | None = None
    chunk_count: int | None = None
    failure_reason: str | None = None
    # Preenchido só nos manuais vindos da pasta da Engenharia (None = enviado pela tela).
    source: SourceFile | None = None

    def __post_init__(self) -> None:
        _validate_names(self.title, self.file_name)
        if self.created_at.tzinfo is None:
            raise InvalidValueError("A data de cadastro precisa ter fuso horário")

    @classmethod
    def register(
        cls, *, title: str, file_name: str, now: datetime, source: SourceFile | None = None
    ) -> Self:
        return cls(
            id=ManualId(uuid4()),
            title=title.strip(),
            file_name=file_name.strip(),
            created_at=now,
            source=source,
        )

    def update_from_source(self, *, title: str, file_name: str, source: SourceFile) -> None:
        """Acompanha o arquivo da pasta: nova revisão, novo título na planilha etc."""
        _validate_names(title, file_name)
        self.title = title.strip()
        self.file_name = file_name.strip()
        self.source = source

    @property
    def is_searchable(self) -> bool:
        return self.status is ManualStatus.INDEXED

    def start_processing(self) -> None:
        if self.status is ManualStatus.PROCESSING:
            raise InvalidStateTransitionError(f"O manual '{self.title}' já está em processamento")
        self.status = ManualStatus.PROCESSING
        self.page_count = None
        self.chunk_count = None
        self.failure_reason = None

    def mark_indexed(self, *, page_count: int, chunk_count: int) -> None:
        self._ensure_processing()
        if page_count < 1 or chunk_count < 1:
            raise InvalidValueError(
                "Um manual indexado precisa ter ao menos uma página e um trecho"
            )
        self.status = ManualStatus.INDEXED
        self.page_count = page_count
        self.chunk_count = chunk_count

    def mark_failed(self, reason: str) -> None:
        self._ensure_processing()
        if not reason.strip():
            raise InvalidValueError("O motivo da falha é obrigatório")
        self.status = ManualStatus.FAILED
        self.failure_reason = reason.strip()

    def _ensure_processing(self) -> None:
        if self.status is not ManualStatus.PROCESSING:
            raise InvalidStateTransitionError(
                f"O manual '{self.title}' não está em processamento (status: {self.status})"
            )

    # Entidades são comparadas pela identidade, não pelos atributos.
    def __eq__(self, other: object) -> bool:
        return isinstance(other, Manual) and other.id == self.id

    def __hash__(self) -> int:
        return hash(self.id)


def _validate_names(title: str, file_name: str) -> None:
    if not title.strip():
        raise InvalidValueError("O título do manual é obrigatório")
    if len(title.strip()) > TITLE_MAX_LENGTH:
        raise InvalidValueError(f"O título do manual excede {TITLE_MAX_LENGTH} caracteres")
    if not file_name.strip():
        raise InvalidValueError("O nome do arquivo do manual é obrigatório")
