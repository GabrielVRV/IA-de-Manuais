from datetime import datetime

import pytest

from manual_assistant.domain.errors import InvalidStateTransitionError, InvalidValueError
from manual_assistant.domain.figures import FigureDescription
from tests.factories import FIXED_NOW, make_manual


def test_a_page_without_technical_content_has_no_text() -> None:
    description = FigureDescription(page=3, text=None, model="m", described_at=FIXED_NOW)

    assert not description.has_content


@pytest.mark.parametrize(
    ("page", "text", "described_at", "tokens"),
    [
        (0, "Figura", FIXED_NOW, 0),
        (1, "   ", FIXED_NOW, 0),
        (1, "Figura", datetime(2026, 1, 1), 0),  # noqa: DTZ001 - sem fuso de propósito
        (1, "Figura", FIXED_NOW, -1),
    ],
)
def test_rejects_invalid_descriptions(
    page: int, text: str, described_at: datetime, tokens: int
) -> None:
    with pytest.raises(InvalidValueError):
        FigureDescription(
            page=page, text=text, model="m", described_at=described_at, input_tokens=tokens
        )


def test_a_scanned_manual_is_indexed_with_figures_only() -> None:
    manual = make_manual()
    manual.start_processing()

    manual.mark_indexed(page_count=9, chunk_count=0, figure_count=9)

    assert (manual.chunk_count, manual.figure_count) == (0, 9)


def test_a_manual_without_text_nor_figures_cannot_be_indexed() -> None:
    manual = make_manual()
    manual.start_processing()

    with pytest.raises(InvalidValueError):
        manual.mark_indexed(page_count=9, chunk_count=0, figure_count=0)


def test_reprocessing_clears_the_figure_count() -> None:
    manual = make_manual()
    manual.start_processing()
    manual.mark_indexed(page_count=2, chunk_count=2, figure_count=1)

    manual.start_processing()

    assert manual.figure_count is None


def test_figures_are_recorded_only_on_indexed_manuals() -> None:
    manual = make_manual()
    with pytest.raises(InvalidStateTransitionError):
        manual.record_figures(3)

    manual.start_processing()
    manual.mark_indexed(page_count=2, chunk_count=2)
    manual.record_figures(3)

    assert manual.figure_count == 3
