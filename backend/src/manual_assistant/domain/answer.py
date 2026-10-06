from collections.abc import Iterable
from dataclasses import dataclass
from typing import Self

from manual_assistant.domain.chunk import Chunk
from manual_assistant.domain.errors import InvalidValueError
from manual_assistant.domain.manual import ManualId


@dataclass(frozen=True, slots=True)
class Citation:
    """Fonte de uma resposta: qual manual e quais páginas embasaram o conteúdo."""

    manual_id: ManualId
    manual_title: str
    pages: tuple[int, ...]  # ordenadas e sem repetição


def cite_sources(chunks: Iterable[Chunk]) -> tuple[Citation, ...]:
    """Agrupa os trechos por manual, mantendo a ordem de relevância e unindo as páginas."""
    titles: dict[ManualId, str] = {}
    pages_by_manual: dict[ManualId, set[int]] = {}
    for chunk in chunks:
        titles.setdefault(chunk.manual_id, chunk.manual_title)
        pages_by_manual.setdefault(chunk.manual_id, set()).update(chunk.pages.numbers)

    return tuple(
        Citation(manual_id=manual_id, manual_title=titles[manual_id], pages=tuple(sorted(pages)))
        for manual_id, pages in pages_by_manual.items()
    )


@dataclass(frozen=True, slots=True)
class Answer:
    text: str
    citations: tuple[Citation, ...] = ()

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise InvalidValueError("Uma resposta não pode ter texto vazio")

    @classmethod
    def based_on(cls, text: str, chunks: Iterable[Chunk]) -> Self:
        return cls(text=text, citations=cite_sources(chunks))

    @property
    def has_sources(self) -> bool:
        return bool(self.citations)
