import pytest

from manual_assistant.domain.answer import Answer, Citation, cite_sources
from manual_assistant.domain.errors import InvalidValueError
from manual_assistant.domain.pages import PageRange
from tests.factories import make_chunk, make_manual


class TestCiteSources:
    def test_groups_chunks_by_manual_and_merges_pages(self) -> None:
        prensa = make_manual("Manual da Prensa")
        torno = make_manual("Manual do Torno")
        chunks = [
            make_chunk(prensa, pages=PageRange(12, 13)),
            make_chunk(torno, pages=PageRange.single(4)),
            make_chunk(prensa, pages=PageRange(3, 3)),
            make_chunk(prensa, pages=PageRange(13, 14)),
        ]

        citations = cite_sources(chunks)

        assert citations == (
            Citation(manual_id=prensa.id, manual_title="Manual da Prensa", pages=(3, 12, 13, 14)),
            Citation(manual_id=torno.id, manual_title="Manual do Torno", pages=(4,)),
        )

    def test_keeps_the_relevance_order_of_manuals(self) -> None:
        first, second = make_manual("Mais relevante"), make_manual("Menos relevante")

        citations = cite_sources([make_chunk(first), make_chunk(second), make_chunk(first)])

        assert [c.manual_title for c in citations] == ["Mais relevante", "Menos relevante"]

    def test_no_chunks_means_no_citations(self) -> None:
        assert cite_sources([]) == ()


class TestAnswer:
    def test_answer_based_on_chunks_cites_them(self) -> None:
        manual = make_manual()

        answer = Answer.based_on("Use óleo ISO VG 68.", [make_chunk(manual)])

        assert answer.has_sources
        assert answer.citations[0].manual_id == manual.id

    def test_answer_without_sources(self) -> None:
        assert not Answer("Não encontrei essa informação nos manuais.").has_sources

    def test_rejects_empty_text(self) -> None:
        with pytest.raises(InvalidValueError):
            Answer("  ")
