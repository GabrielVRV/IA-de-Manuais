from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from manual_assistant.infrastructure.persistence.login_attempt_repository import (
    SqlAlchemyLoginAttemptRepository,
)
from tests.factories import FIXED_NOW

pytestmark = [pytest.mark.db, pytest.mark.anyio]

LOCKOUT = timedelta(minutes=15)


async def test_counts_locks_and_clears(session_factory: async_sessionmaker[AsyncSession]) -> None:
    repository = SqlAlchemyLoginAttemptRepository(session_factory)
    attempts = await repository.get("joao")
    assert attempts.failed_count == 0

    for _ in range(2):
        attempts.record_failure(FIXED_NOW, max_attempts=2, lockout=LOCKOUT)
        await repository.save(attempts)

    assert (await repository.get("joao")).is_locked(FIXED_NOW)

    await repository.clear("joao")
    assert (await repository.get("joao")).locked_until is None
