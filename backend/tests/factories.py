"""Construtores de objetos de domínio válidos para testes (só informe o que importa)."""

from datetime import UTC, datetime

from manual_assistant.domain.chunk import Chunk
from manual_assistant.domain.manual import Manual
from manual_assistant.domain.pages import PageRange

FIXED_NOW = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)


def make_manual(title: str = "Manual da Prensa P-200", file_name: str = "p200.pdf") -> Manual:
    return Manual.register(title=title, file_name=file_name, now=FIXED_NOW)


def make_chunk(
    manual: Manual | None = None,
    *,
    text: str = "Verifique a pressão do óleo antes de ligar.",
    pages: PageRange | None = None,
    position: int = 0,
) -> Chunk:
    return Chunk.create(
        manual=manual or make_manual(),
        text=text,
        pages=pages or PageRange.single(1),
        position=position,
    )
