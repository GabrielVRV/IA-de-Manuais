import pytest

from manual_assistant.domain.pages import Page, PageRange
from manual_assistant.infrastructure.documents.line_chunker import LineChunker


def texts(chunker: LineChunker, *pages: Page) -> list[str]:
    return [fragment.text for fragment in chunker.split(pages)]


def test_small_document_becomes_a_single_fragment() -> None:
    fragments = LineChunker(max_chars=100, overlap_chars=20).split(
        [Page(1, "Linha um\nLinha dois")]
    )

    assert [(f.text, f.pages) for f in fragments] == [("Linha um\nLinha dois", PageRange(1, 1))]


def test_normalizes_whitespace_and_skips_empty_lines() -> None:
    chunker = LineChunker(max_chars=100, overlap_chars=20)

    assert texts(chunker, Page(1, "  Pressão   máxima:\t180 bar \n\n   \nFim")) == [
        "Pressão máxima: 180 bar\nFim"
    ]


def test_packs_lines_up_to_the_limit_without_breaking_them() -> None:
    chunker = LineChunker(max_chars=11, overlap_chars=0)

    assert texts(chunker, Page(1, "aaaa\nbbbb\ncccc\ndddd")) == ["aaaa\nbbbb", "cccc\ndddd"]


def test_repeats_the_end_of_the_previous_fragment_as_overlap() -> None:
    chunker = LineChunker(max_chars=14, overlap_chars=4)

    assert texts(chunker, Page(1, "aaaa\nbbbb\ncccc\ndddd")) == [
        "aaaa\nbbbb\ncccc",
        "cccc\ndddd",
    ]


def test_skips_overlap_that_would_not_leave_room_for_the_next_line() -> None:
    chunker = LineChunker(max_chars=10, overlap_chars=4)

    assert texts(chunker, Page(1, "aaaa\nbbbb\ncccccccc")) == ["aaaa\nbbbb", "cccccccc"]


def test_fragments_can_span_pages_and_record_the_range() -> None:
    chunker = LineChunker(max_chars=100, overlap_chars=20)

    fragments = chunker.split([Page(4, "fim da seção"), Page(5, "continuação")])

    assert fragments[0].pages == PageRange(4, 5)


def test_blank_pages_produce_no_fragments() -> None:
    assert LineChunker().split([Page(1, ""), Page(2, "  \n ")]) == []


def test_splits_long_lines_between_words() -> None:
    chunker = LineChunker(max_chars=10, overlap_chars=0)

    assert texts(chunker, Page(1, "uma frase longa demais aqui")) == [
        "uma frase",
        "longa",
        "demais",
        "aqui",
    ]


def test_hard_splits_words_longer_than_the_limit() -> None:
    chunker = LineChunker(max_chars=4, overlap_chars=0)

    assert texts(chunker, Page(1, "ab abcdefgh cd")) == ["ab", "abcd", "efgh", "cd"]


def test_no_fragment_exceeds_the_limit() -> None:
    chunker = LineChunker(max_chars=50, overlap_chars=15)
    page = Page(1, "\n".join(f"Item {i}: verificar componente número {i * 7}" for i in range(40)))

    fragments = chunker.split([page])

    assert len(fragments) > 1
    assert all(len(f.text) <= 50 for f in fragments)


@pytest.mark.parametrize(("max_chars", "overlap"), [(0, 0), (10, 10), (10, -1)])
def test_rejects_invalid_configuration(max_chars: int, overlap: int) -> None:
    with pytest.raises(ValueError, match="precisa"):
        LineChunker(max_chars=max_chars, overlap_chars=overlap)


def test_a_fragment_that_starts_mid_section_carries_the_section_titles() -> None:
    chunker = LineChunker(max_chars=120, overlap_chars=0)
    page = Page(
        1,
        "1.2 Relações de Códigos:\n"
        "1.2.5.1 Acionamento Motoredutor:\n"
        "Trifásico 220/380V Monofásico 110/220V\n"
        "20.400.309 Acionamento 0,5CV 60Hz\n"
        "20.400.311 Acionamento 1,0CV 60Hz\n"
        "20.400.317 Acionamento 0,5CV 50Hz",
    )

    first, second = texts(chunker, page)

    assert first.startswith("1.2 Relações")  # o primeiro já começa pelo título
    assert second.splitlines()[0] == (
        "[Seção: 1.2 Relações de Códigos: > 1.2.5.1 Acionamento Motoredutor:]"
    )


@pytest.mark.parametrize(
    "line",
    [
        "20.400.319 Acionamento 1,0CV 50Hz",  # código de peça
        "4 Saídas Retas Paralelas",  # item de lista, sem ponto
        "3.30 m de altura",  # medida
        "22 02.017.076 5m CABO PP",  # linha de lista de peças
    ],
)
def test_codes_and_part_lists_are_not_section_titles(line: str) -> None:
    chunker = LineChunker(max_chars=40, overlap_chars=0)

    fragments = texts(chunker, Page(1, f"{line}\n{'x' * 30}\n{'y' * 30}"))

    assert not any(text.startswith("[Seção") for text in fragments)
