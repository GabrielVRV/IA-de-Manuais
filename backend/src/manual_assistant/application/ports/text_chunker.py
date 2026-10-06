from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from manual_assistant.domain.pages import Page, PageRange


@dataclass(frozen=True, slots=True)
class TextFragment:
    """Pedaço de texto produzido pelo divisor, ainda sem identidade de trecho."""

    text: str
    pages: PageRange


class TextChunker(Protocol):
    """Divide o texto das páginas em fragmentos do tamanho ideal para busca semântica."""

    def split(self, pages: Sequence[Page]) -> Sequence[TextFragment]: ...
