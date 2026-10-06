import math

import pytest

from manual_assistant.domain.chunk import ScoredChunk
from manual_assistant.domain.errors import InvalidValueError
from manual_assistant.domain.pages import PageRange
from tests.factories import make_chunk, make_manual


class TestChunk:
    def test_carries_its_manual_reference(self) -> None:
        manual = make_manual("Manual do Torno T-10")

        chunk = make_chunk(manual, pages=PageRange(2, 3), position=4)

        assert chunk.manual_id == manual.id
        assert chunk.manual_title == "Manual do Torno T-10"
        assert chunk.pages == PageRange(2, 3)
        assert chunk.position == 4

    def test_rejects_empty_text(self) -> None:
        with pytest.raises(InvalidValueError):
            make_chunk(text="  \n ")

    def test_rejects_negative_position(self) -> None:
        with pytest.raises(InvalidValueError):
            make_chunk(position=-1)


class TestScoredChunk:
    @pytest.mark.parametrize("score", [0.0, 0.5, 1.0])
    def test_accepts_scores_between_zero_and_one(self, score: float) -> None:
        assert ScoredChunk(make_chunk(), score).score == score

    @pytest.mark.parametrize("score", [-0.1, 1.01, math.nan, math.inf])
    def test_rejects_scores_out_of_range(self, score: float) -> None:
        with pytest.raises(InvalidValueError):
            ScoredChunk(make_chunk(), score)
