import math
from dataclasses import dataclass
from enum import StrEnum
from typing import NewType, Self
from uuid import UUID, uuid4

from manual_assistant.domain.errors import InvalidValueError
from manual_assistant.domain.manual import Manual, ManualId
from manual_assistant.domain.pages import PageRange

ChunkId = NewType("ChunkId", UUID)


class ChunkKind(StrEnum):
    """De onde veio o texto do trecho."""

    TEXT = "text"  # texto extraído do PDF
    FIGURE = "figure"  # descrição, gerada por IA, das figuras e desenhos de uma página


@dataclass(frozen=True, kw_only=True, slots=True)
class Chunk:
    """Trecho de um manual: a unidade que é indexada, buscada e citada."""

    id: ChunkId
    manual_id: ManualId
    # Desnormalizado de propósito: permite citar a fonte sem consultar o repositório.
    manual_title: str
    text: str
    pages: PageRange
    position: int  # ordem do trecho dentro do manual (e do tipo), a partir de 0
    kind: ChunkKind = ChunkKind.TEXT

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise InvalidValueError("Um trecho não pode ter texto vazio")
        if self.position < 0:
            raise InvalidValueError("A posição do trecho não pode ser negativa")

    @classmethod
    def create(
        cls,
        *,
        manual: Manual,
        text: str,
        pages: PageRange,
        position: int,
        kind: ChunkKind = ChunkKind.TEXT,
    ) -> Self:
        return cls(
            id=ChunkId(uuid4()),
            manual_id=manual.id,
            manual_title=manual.title,
            text=text,
            pages=pages,
            position=position,
            kind=kind,
        )


@dataclass(frozen=True, slots=True)
class ScoredChunk:
    """Trecho encontrado numa busca, com sua relevância para a pergunta."""

    chunk: Chunk
    score: float  # similaridade normalizada: 0 (nada a ver) a 1 (idêntico)

    def __post_init__(self) -> None:
        if not (math.isfinite(self.score) and 0.0 <= self.score <= 1.0):
            raise InvalidValueError(f"A relevância deve estar entre 0 e 1 (recebido: {self.score})")
