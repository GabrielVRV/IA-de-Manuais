from dataclasses import dataclass
from typing import Self

from manual_assistant.domain.errors import InvalidValueError


@dataclass(frozen=True, slots=True)
class PageRange:
    """Intervalo contínuo de páginas de um manual (inclusivo nas duas pontas)."""

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 1:
            raise InvalidValueError(f"A numeração de páginas começa em 1 (recebido: {self.start})")
        if self.end < self.start:
            raise InvalidValueError(
                f"Página final ({self.end}) não pode ser anterior à inicial ({self.start})"
            )

    @classmethod
    def single(cls, page: int) -> Self:
        return cls(page, page)

    @property
    def numbers(self) -> range:
        return range(self.start, self.end + 1)


@dataclass(frozen=True, slots=True)
class Page:
    """Texto extraído de uma página do documento original."""

    number: int
    text: str

    def __post_init__(self) -> None:
        if self.number < 1:
            raise InvalidValueError(f"A numeração de páginas começa em 1 (recebido: {self.number})")

    @property
    def is_blank(self) -> bool:
        return not self.text.strip()
