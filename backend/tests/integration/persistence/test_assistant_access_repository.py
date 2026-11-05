import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from manual_assistant.domain.assistant import (
    AccessPolicy,
    AssistantId,
    DefaultAccess,
    UserAccess,
)
from manual_assistant.infrastructure.persistence.assistant_access_repository import (
    SqlAlchemyAssistantAccessRepository,
)
from manual_assistant.infrastructure.persistence.user_repository import SqlAlchemyUserRepository
from tests.factories import FIXED_NOW
from tests.security import make_user

pytestmark = [pytest.mark.db, pytest.mark.anyio]

ENGINEERING = AssistantId.ENGINEERING


async def test_policy_starts_open_and_keeps_what_is_saved(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlAlchemyAssistantAccessRepository(session_factory)

    assert await repository.get_policy(ENGINEERING) == AccessPolicy(assistant_id=ENGINEERING)

    for default in (DefaultAccess.RESTRICTED, DefaultAccess.OPEN):
        policy = AccessPolicy(
            assistant_id=ENGINEERING,
            default_access=default,
            request_instructions="Abra um chamado no GLPI.",
            updated_at=FIXED_NOW,
            updated_by="Ana Admin",
        )
        await repository.save_policy(policy)
        assert await repository.get_policy(ENGINEERING) == policy


async def test_user_exceptions_are_saved_changed_and_removed(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlAlchemyAssistantAccessRepository(session_factory)
    users = SqlAlchemyUserRepository(session_factory)
    maria, joao = make_user("maria"), make_user("joao")
    await users.save(maria)
    await users.save(joao)

    await repository.set_user_access(maria.id, ENGINEERING, UserAccess.GRANTED)
    await repository.set_user_access(joao.id, ENGINEERING, UserAccess.GRANTED)
    await repository.set_user_access(joao.id, ENGINEERING, UserAccess.DENIED)

    assert await repository.user_access(maria.id) == {ENGINEERING: UserAccess.GRANTED}
    assert await repository.all_user_access() == {
        maria.id: {ENGINEERING: UserAccess.GRANTED},
        joao.id: {ENGINEERING: UserAccess.DENIED},
    }

    await repository.set_user_access(maria.id, ENGINEERING, None)
    await repository.set_user_access(maria.id, ENGINEERING, None)  # já removida: sem erro

    assert await repository.user_access(maria.id) == {}
    assert set(await repository.all_user_access()) == {joao.id}
