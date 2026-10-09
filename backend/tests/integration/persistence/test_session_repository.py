from datetime import timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from manual_assistant.domain.session import Session
from manual_assistant.infrastructure.persistence.session_repository import (
    SqlAlchemySessionRepository,
)
from manual_assistant.infrastructure.persistence.user_repository import SqlAlchemyUserRepository
from tests.factories import FIXED_NOW
from tests.security import make_user

pytestmark = [pytest.mark.db, pytest.mark.anyio]


@pytest.fixture
def repository(session_factory: async_sessionmaker[AsyncSession]) -> SqlAlchemySessionRepository:
    return SqlAlchemySessionRepository(session_factory)


async def new_session(
    session_factory: async_sessionmaker[AsyncSession], token_hash: str, *, days_ago: int = 0
) -> Session:
    user = make_user(f"user-{token_hash}")
    await SqlAlchemyUserRepository(session_factory).save(user)
    moment = FIXED_NOW - timedelta(days=days_ago)
    return Session(token_hash=token_hash, user_id=user.id, created_at=moment, last_seen_at=moment)


async def test_round_trip_touch_and_delete(
    repository: SqlAlchemySessionRepository, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    session = await new_session(session_factory, "abc")
    await repository.add(session)

    await repository.touch("abc", FIXED_NOW + timedelta(hours=1))
    restored = await repository.get("abc")

    assert restored is not None
    assert restored.user_id == session.user_id
    assert restored.last_seen_at == FIXED_NOW + timedelta(hours=1)

    await repository.delete("abc")
    assert await repository.get("abc") is None


async def test_deletes_only_expired_sessions(
    repository: SqlAlchemySessionRepository, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    for session in (
        await new_session(session_factory, "fresh"),
        await new_session(session_factory, "idle", days_ago=10),
    ):
        await repository.add(session)

    await repository.delete_expired(
        last_seen_before=FIXED_NOW - timedelta(days=7),
        created_before=FIXED_NOW - timedelta(days=30),
    )

    assert await repository.get("fresh") is not None
    assert await repository.get("idle") is None


async def test_removing_a_user_removes_their_sessions(
    repository: SqlAlchemySessionRepository, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    session = await new_session(session_factory, "abc")
    await repository.add(session)

    async with session_factory.begin() as db:
        await db.execute(text("DELETE FROM users"))

    assert await repository.get("abc") is None
