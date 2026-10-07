from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from manual_assistant.application.ports.text_chunker import TextFragment
from manual_assistant.domain.pages import Page, PageRange

DEFAULT_MAX_CHARS = 1500  # ~375 tokens: contexto suficiente sem diluir o significado
DEFAULT_OVERLAP_CHARS = 200  # repete o fim do trecho anterior para não cortar uma ideia ao meio


@dataclass(frozen=True, slots=True)
class _Line:
    text: str
    page: int


class LineChunker:
    """Agrupa linhas consecutivas em trechos de até ``max_chars`` caracteres.

    Trabalha com linhas (e não parágrafos) porque o texto extraído de PDFs não preserva
    linhas em branco, e porque assim listas e tabelas mantêm sua estrutura. Um trecho
    pode atravessar páginas; o intervalo de páginas é registrado para a citação.
    """

    def __init__(
        self,
        max_chars: int = DEFAULT_MAX_CHARS,
        overlap_chars: int = DEFAULT_OVERLAP_CHARS,
    ) -> None:
        if max_chars < 1:
            raise ValueError("max_chars precisa ser positivo")
        if not 0 <= overlap_chars < max_chars:
            raise ValueError("overlap_chars precisa estar entre 0 e max_chars")
        self._max_chars = max_chars
        self._overlap_chars = overlap_chars

    def split(self, pages: Sequence[Page]) -> list[TextFragment]:
        fragments: list[TextFragment] = []
        current: list[_Line] = []

        for line in self._lines(pages):
            if current and _length(current) + 1 + len(line.text) > self._max_chars:
                fragments.append(_to_fragment(current))
                current = self._overlap(current, incoming=len(line.text))
            current.append(line)

        if current:
            fragments.append(_to_fragment(current))
        return fragments

    def _lines(self, pages: Sequence[Page]) -> Iterator[_Line]:
        for page in pages:
            for raw_line in page.text.splitlines():
                text = " ".join(raw_line.split())  # normaliza espaços repetidos
                for piece in self._fit(text):
                    yield _Line(piece, page.number)

    def _fit(self, text: str) -> Iterator[str]:
        """Quebra linhas maiores que o limite, de preferência entre palavras."""
        if len(text) <= self._max_chars:
            if text:
                yield text
            return
        piece = ""
        for word in text.split(" "):
            while len(word) > self._max_chars:  # palavra gigante (ex.: sequência sem espaços)
                if piece:
                    yield piece
                    piece = ""
                yield word[: self._max_chars]
                word = word[self._max_chars :]
            if not word:
                continue
            candidate = f"{piece} {word}" if piece else word
            if len(candidate) > self._max_chars:
                yield piece
                piece = word
            else:
                piece = candidate
        if piece:
            yield piece

    def _overlap(self, lines: list[_Line], *, incoming: int) -> list[_Line]:
        """Últimas linhas do trecho que cabem na sobreposição e ainda deixam espaço."""
        carried: list[_Line] = []
        for line in reversed(lines):
            size = _length([line, *carried])
            if size > self._overlap_chars or size + 1 + incoming > self._max_chars:
                break
            carried.insert(0, line)
        return carried


def _length(lines: Sequence[_Line]) -> int:
    return sum(len(line.text) for line in lines) + max(len(lines) - 1, 0)


def _to_fragment(lines: Sequence[_Line]) -> TextFragment:
    return TextFragment(
        text="\n".join(line.text for line in lines),
        pages=PageRange(min(line.page for line in lines), max(line.page for line in lines)),
    )
