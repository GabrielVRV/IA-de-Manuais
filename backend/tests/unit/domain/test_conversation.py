from datetime import timedelta
from uuid import uuid4

import pytest

from manual_assistant.domain.answer import Answer
from manual_assistant.domain.conversation import (
    AUTO_TITLE_LENGTH,
    TITLE_MAX_LENGTH,
    Conversation,
    RetentionPolicy,
    title_from,
)
from manual_assistant.domain.errors import InvalidValueError
from manual_assistant.domain.question import Question
from manual_assistant.domain.user import UserId
from tests.factories import FIXED_NOW

OWNER = UserId(uuid4())


def start(question: str = "Qual a pressão máxima da P-200?") -> Conversation:
    return Conversation.start(OWNER, Question(question), FIXED_NOW)


class TestTitle:
    def test_short_first_question_becomes_the_title(self) -> None:
        assert start("  Qual a pressão   máxima? ").title == "Qual a pressão máxima?"

    def test_long_question_is_cut_on_a_whole_word(self) -> None:
        question = Question("Como faço a manutenção preventiva completa " + "do redutor " * 10)

        title = title_from(question)

        assert len(title) <= AUTO_TITLE_LENGTH
        assert title == "Como faço a manutenção preventiva completa do redutor do…"

    def test_rename_normalizes_spaces(self) -> None:
        conversation = start()

        conversation.rename("  Pressão   da P-200 ")

        assert conversation.title == "Pressão da P-200"

    @pytest.mark.parametrize("title", ["", "   ", "x" * (TITLE_MAX_LENGTH + 1)])
    def test_rejects_invalid_titles(self, title: str) -> None:
        with pytest.raises(InvalidValueError):
            start().rename(title)


class TestExchanges:
    def test_record_appends_and_moves_the_conversation_to_the_top(self) -> None:
        conversation = start()
        later = FIXED_NOW + timedelta(minutes=5)

        exchange = conversation.record(Question("E a mínima?"), Answer("20 bar."), later)

        assert conversation.exchanges == [exchange]
        assert exchange.question == "E a mínima?"
        assert conversation.updated_at == later

    def test_recent_returns_the_last_exchanges_in_order(self) -> None:
        conversation = start()
        for n in range(5):
            conversation.record(Question(f"Pergunta {n}"), Answer(f"Resposta {n}"), FIXED_NOW)

        assert [e.question for e in conversation.recent(2)] == ["Pergunta 3", "Pergunta 4"]
        assert conversation.recent(0) == ()

    def test_only_the_owner_owns_it(self) -> None:
        conversation = start()

        assert conversation.is_owned_by(OWNER)
        assert not conversation.is_owned_by(UserId(uuid4()))


class TestRetentionPolicy:
    def test_cutoff_is_now_minus_the_idle_limit(self) -> None:
        policy = RetentionPolicy(max_idle=timedelta(days=90))

        assert policy.cutoff(FIXED_NOW) == FIXED_NOW - timedelta(days=90)

    def test_no_limit_keeps_everything(self) -> None:
        assert RetentionPolicy(max_idle=None).cutoff(FIXED_NOW) is None
