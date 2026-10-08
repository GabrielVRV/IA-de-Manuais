from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from manual_assistant.application.errors import UserAlreadyExistsError
from manual_assistant.cli import create_admin
from manual_assistant.domain.user import UserId, UserRole
from manual_assistant.infrastructure.persistence.user_repository import SqlAlchemyUserRepository
from manual_assistant.infrastructure.settings import Settings
from tests.factories import FIXED_NOW
from tests.security import fast_hasher, make_user

pytestmark = [pytest.mark.db, pytest.mark.anyio]


@pytest.fixture
def repository(session_factory: async_sessionmaker[AsyncSession]) -> SqlAlchemyUserRepository:
    return SqlAlchemyUserRepository(session_factory)


async def test_saves_and_restores_every_field(repository: SqlAlchemyUserRepository) -> None:
    user = make_user("maria", role=UserRole.ADMIN, must_change_password=True)
    user.record_failed_login(FIXED_NOW, max_attempts=1, lockout=timedelta(minutes=5))
    user.last_login_at = FIXED_NOW

    await repository.save(user)
    restored = await repository.get(user.id)

    assert restored is not None
    assert (
        restored.username,
        restored.display_name,
        restored.role,
        restored.password_hash,
        restored.is_active,
        restored.must_change_password,
        restored.locked_until,
        restored.last_login_at,
        restored.created_at,
    ) == (
        "maria",
        "Maria",
        UserRole.ADMIN,
        user.password_hash,
        True,
        True,
        FIXED_NOW + timedelta(minutes=5),
        FIXED_NOW,
        FIXED_NOW,
    )


async def test_updates_and_finds_by_username(repository: SqlAlchemyUserRepository) -> None:
    user = make_user("joao")
    await repository.save(user)

    user.deactivate()
    await repository.save(user)

    found = await repository.get_by_username("joao")
    assert found is not None
    assert not found.is_active
    assert await repository.get_by_username("ninguem") is None
    assert await repository.get(UserId(uuid4())) is None


async def test_the_database_rejects_duplicate_logins(repository: SqlAlchemyUserRepository) -> None:
    original = make_user("ana")
    await repository.save(original)
    duplicate = replace(make_user("ana"), id=UserId(uuid4()))

    with pytest.raises(UserAlreadyExistsError):
        await repository.save(duplicate)


async def test_lists_in_alphabetical_order(repository: SqlAlchemyUserRepository) -> None:
    for username in ("zeca", "ana", "maria"):
        await repository.save(make_user(username))

    assert [u.username for u in await repository.list_all()] == ["ana", "maria", "zeca"]


async def test_cli_creates_an_admin_with_a_final_password(
    postgres_settings: Settings, repository: SqlAlchemyUserRepository
) -> None:
    await create_admin(postgres_settings, "Gabriel", "Gabriel", "senha-definitiva")

    admin = await repository.get_by_username("gabriel")
    assert admin is not None
    assert admin.is_admin
    assert not admin.must_change_password
    assert fast_hasher().verify("senha-definitiva", admin.password_hash)
