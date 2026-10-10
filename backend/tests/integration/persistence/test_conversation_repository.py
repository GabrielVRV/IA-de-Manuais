from datetime import timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from manual_assistant.domain.answer import Answer, Citation
from manual_assistant.domain.conversation import Conversation
from manual_assistant.domain.question import Question
from manual_assistant.domain.user import User
from manual_assistant.infrastructure.persistence.conversation_repository import (
    SqlAlchemyConversationRepository,
)
from manual_assistant.infrastructure.persistence.user_repository import SqlAlchemyUserRepository
from tests.factories import FIXED_NOW, make_manual
from tests.security import make_user

pytestmark = [pytest.mark.db, pytest.mark.anyio]

manual = make_manual("Manual da Prensa P-200")
ANSWER = Answer(
    "A pressão máxima é 180 bar.",
    citations=(Citation(manual_id=manual.id, manual_title=manual.title, pages=(12, 13)),),
)


@pytest.fixture
def repository(
    session_factory: async_sessionmaker[AsyncSession],
) -> SqlAlchemyConversationRepository:
    return SqlAlchemyConversationRepository(session_factory)


async def saved_user(session_factory: async_sessionmaker[AsyncSession], username: str) -> User:
    user = make_user(username)
    await SqlAlchemyUserRepository(session_factory).save(user)
    return user


def conversation_of(
    user: User, question: str = "Qual a pressão máxima?", *, days_ago: int = 0
) -> Conversation:
    moment = FIXED_NOW - timedelta(days=days_ago)
    conversation = Conversation.start(user.id, Question(question), moment)
    conversation.record(Question(question), ANSWER, moment)
    return conversation


async def test_round_trip_with_exchanges_and_citations(
    repository: SqlAlchemyConversationRepository,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    maria = await saved_user(session_factory, "maria")
    conversation = conversation_of(maria)
    await repository.add(conversation)

    follow_up = conversation.record(
        Question("E a mínima?"), Answer("20 bar."), FIXED_NOW + timedelta(minutes=3)
    )
    await repository.append(conversation, follow_up)
    restored = await repository.get(conversation.id)

    assert restored is not None
    assert restored.owner_id == maria.id
    assert restored.title == "Qual a pressão máxima?"
    assert restored.updated_at == FIXED_NOW + timedelta(minutes=3)
    assert [e.question for e in restored.exchanges] == ["Qual a pressão máxima?", "E a mínima?"]
    assert restored.exchanges[0].answer == ANSWER
    assert restored.exchanges[1].answer.citations == ()


async def test_lists_by_owner_most_recent_first_with_counts(
    repository: SqlAlchemyConversationRepository,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    maria = await saved_user(session_factory, "maria")
    joao = await saved_user(session_factory, "joao")
    old = conversation_of(maria, "Pergunta antiga", days_ago=3)
    new = conversation_of(maria, "Pergunta nova")
    for conversation in (old, new, conversation_of(joao)):
        await repository.add(conversation)

    summaries = await repository.list_by_owner(maria.id)

    assert [(s.title, s.exchange_count) for s in summaries] == [
        ("Pergunta nova", 1),
        ("Pergunta antiga", 1),
    ]


async def test_renames_and_deletes_with_its_exchanges(
    repository: SqlAlchemyConversationRepository,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    conversation = conversation_of(await saved_user(session_factory, "maria"))
    await repository.add(conversation)

    await repository.rename(conversation.id, "Pressão da P-200")
    renamed = await repository.get(conversation.id)
    await repository.delete(conversation.id)

    assert renamed is not None
    assert renamed.title == "Pressão da P-200"
    assert await repository.get(conversation.id) is None


async def test_deletes_only_idle_conversations(
    repository: SqlAlchemyConversationRepository,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    maria = await saved_user(session_factory, "maria")
    old = conversation_of(maria, days_ago=100)
    recent = conversation_of(maria, days_ago=5)
    await repository.add(old)
    await repository.add(recent)

    removed = await repository.delete_idle(updated_before=FIXED_NOW - timedelta(days=90))

    assert removed == 1
    assert await repository.get(old.id) is None
    assert await repository.get(recent.id) is not None


async def test_deleting_the_user_deletes_the_conversations(
    repository: SqlAlchemyConversationRepository,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    maria = await saved_user(session_factory, "maria")
    conversation = conversation_of(maria)
    await repository.add(conversation)

    async with session_factory.begin() as db:
        await db.execute(text("DELETE FROM users WHERE id = :id"), {"id": maria.id})

    assert await repository.get(conversation.id) is None
