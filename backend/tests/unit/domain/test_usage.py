from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from manual_assistant.domain.errors import InvalidValueError
from manual_assistant.domain.usage import (
    MODEL_NAME_MAX_LENGTH,
    PRICE_MAX,
    ModelPrice,
    QuestionUsage,
)
from manual_assistant.domain.user import UserId
from tests.factories import FIXED_NOW

USER = UserId(uuid4())


class TestQuestionUsage:
    def test_counts_input_and_output_tokens(self) -> None:
        usage = QuestionUsage(USER, FIXED_NOW, "gpt-4.1-mini", input_tokens=900, output_tokens=100)

        assert usage.total_tokens == 1000

    def test_question_answered_without_the_model_spends_nothing(self) -> None:
        assert QuestionUsage(USER, FIXED_NOW, model=None).total_tokens == 0

    def test_tokens_spent_require_the_model(self) -> None:
        with pytest.raises(InvalidValueError):
            QuestionUsage(USER, FIXED_NOW, model=None, input_tokens=10)

    def test_rejects_negative_tokens(self) -> None:
        with pytest.raises(InvalidValueError):
            QuestionUsage(USER, FIXED_NOW, "gpt-4.1-mini", input_tokens=-1)

    def test_requires_a_timezone(self) -> None:
        with pytest.raises(InvalidValueError):
            QuestionUsage(USER, datetime(2026, 11, 5, 12, 0), "gpt-4.1-mini")  # noqa: DTZ001

    @pytest.mark.parametrize("model", ["", "   ", "m" * (MODEL_NAME_MAX_LENGTH + 1)])
    def test_rejects_invalid_model_names(self, model: str) -> None:
        with pytest.raises(InvalidValueError):
            QuestionUsage(USER, FIXED_NOW, model)


class TestModelPrice:
    def test_cost_is_proportional_to_the_price_per_million_tokens(self) -> None:
        price = ModelPrice("gpt-4.1-mini", Decimal("0.40"), Decimal("1.60"))

        cost = price.cost(input_tokens=1_000_000, output_tokens=500_000)

        assert cost == Decimal("1.20")

    def test_free_model_costs_nothing(self) -> None:
        price = ModelPrice("modelo-local", Decimal(0), Decimal(0))

        assert price.cost(input_tokens=5_000, output_tokens=5_000) == 0

    @pytest.mark.parametrize(
        "value", [Decimal(-1), PRICE_MAX + 1, Decimal("NaN"), Decimal("Infinity")]
    )
    def test_rejects_prices_out_of_range(self, value: Decimal) -> None:
        with pytest.raises(InvalidValueError):
            ModelPrice("gpt-4.1-mini", value, Decimal(1))
        with pytest.raises(InvalidValueError):
            ModelPrice("gpt-4.1-mini", Decimal(1), value)

    def test_requires_the_model_name(self) -> None:
        with pytest.raises(InvalidValueError):
            ModelPrice(" ", Decimal(1), Decimal(1))
