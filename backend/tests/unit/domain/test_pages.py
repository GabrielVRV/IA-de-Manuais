import pytest

from manual_assistant.domain.errors import InvalidValueError
from manual_assistant.domain.pages import Page, PageRange


class TestPageRange:
    def test_lists_every_page_in_the_range(self) -> None:
        assert list(PageRange(3, 5).numbers) == [3, 4, 5]

    def test_single_page(self) -> None:
        assert PageRange.single(7) == PageRange(7, 7)

    @pytest.mark.parametrize(("start", "end"), [(0, 1), (-1, 2), (5, 4)])
    def test_rejects_invalid_ranges(self, start: int, end: int) -> None:
        with pytest.raises(InvalidValueError):
            PageRange(start, end)


class TestPage:
    def test_rejects_page_number_below_one(self) -> None:
        with pytest.raises(InvalidValueError):
            Page(number=0, text="texto")

    @pytest.mark.parametrize(("text", "blank"), [("", True), ("  \n\t", True), ("Sumário", False)])
    def test_detects_blank_pages(self, text: str, blank: bool) -> None:
        assert Page(number=1, text=text).is_blank is blank
