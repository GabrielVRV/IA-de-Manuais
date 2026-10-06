import pytest

from manual_assistant.domain.errors import InvalidValueError
from manual_assistant.domain.question import QUESTION_MAX_LENGTH, Question


def test_trims_surrounding_whitespace() -> None:
    assert Question("  Qual a pressão ideal do óleo?\n").text == "Qual a pressão ideal do óleo?"


@pytest.mark.parametrize("text", ["", "   ", "oi", "x" * (QUESTION_MAX_LENGTH + 1)])
def test_rejects_too_short_or_too_long_questions(text: str) -> None:
    with pytest.raises(InvalidValueError):
        Question(text)


def test_accepts_the_maximum_length() -> None:
    assert len(Question("x" * QUESTION_MAX_LENGTH).text) == QUESTION_MAX_LENGTH
