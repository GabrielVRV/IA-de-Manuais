from uuid import uuid4

import pytest

from manual_assistant.application.errors import (
    PermissionDeniedError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from manual_assistant.application.use_cases.manage_users import (
    CreateUserUseCase,
    ListUsersUseCase,
    ResetUserPasswordUseCase,
    UpdateUserUseCase,
    UseTotvsLoginUseCase,
)
from manual_assistant.domain.errors import InvalidValueError
from manual_assistant.domain.user import AuthSource, UserId, UserRole
from tests.factories import FIXED_NOW
from tests.fakes import InMemoryUserRepository
from tests.security import fast_hasher, make_totvs_user, make_user

pytestmark = pytest.mark.anyio

admin = make_user("admin", role=UserRole.ADMIN)
common = make_user("joao")


@pytest.fixture
def users() -> InMemoryUserRepository:
    return InMemoryUserRepository()


def create_use_case(users: InMemoryUserRepository) -> CreateUserUseCase:
    return CreateUserUseCase(users=users, hasher=fast_hasher(), clock=lambda: FIXED_NOW)


class TestCreate:
    async def test_admin_creates_a_user_with_a_temporary_password(
        self, users: InMemoryUserRepository
    ) -> None:
        user = await create_use_case(users).execute(
            admin,
            username="Maria",
            display_name="Maria Silva",
            role=UserRole.USER,
            temporary_password="provisoria-1",
        )

        assert user.username == "maria"
        assert user.must_change_password
        assert await users.get_by_username("maria") is user

    async def test_system_creation_keeps_the_chosen_password(
        self, users: InMemoryUserRepository
    ) -> None:
        user = await create_use_case(users).execute_as_system(
            username="gabriel",
            display_name="Gabriel",
            role=UserRole.ADMIN,
            password="senha-definitiva",
        )

        assert user.is_admin
        assert not user.must_change_password

    async def test_only_admins_can_create(self, users: InMemoryUserRepository) -> None:
        with pytest.raises(PermissionDeniedError):
            await create_use_case(users).execute(
                common,
                username="x123",
                display_name="X",
                role=UserRole.USER,
                temporary_password="provisoria-1",
            )

    async def test_rejects_duplicate_logins_regardless_of_case(
        self, users: InMemoryUserRepository
    ) -> None:
        await users.save(make_user("maria"))

        with pytest.raises(UserAlreadyExistsError):
            await create_use_case(users).execute(
                admin,
                username="MARIA",
                display_name="Outra",
                role=UserRole.USER,
                temporary_password="provisoria-1",
            )

    async def test_enforces_the_password_policy(self, users: InMemoryUserRepository) -> None:
        with pytest.raises(InvalidValueError, match="ao menos 8"):
            await create_use_case(users).execute(
                admin,
                username="maria",
                display_name="Maria",
                role=UserRole.USER,
                temporary_password="123",
            )


async def test_lists_users_for_admins_only(users: InMemoryUserRepository) -> None:
    await users.save(common)

    assert await ListUsersUseCase(users).execute(admin) == [common]
    with pytest.raises(PermissionDeniedError):
        await ListUsersUseCase(users).execute(common)


async def test_resets_a_password(users: InMemoryUserRepository) -> None:
    user = make_user("ana")
    await users.save(user)
    hasher = fast_hasher()

    await ResetUserPasswordUseCase(users=users, hasher=hasher).execute(
        admin, user.id, temporary_password="provisoria-2"
    )

    assert user.must_change_password
    assert user.password_hash is not None
    assert hasher.verify("provisoria-2", user.password_hash)


async def test_totvs_passwords_cannot_be_reset_here(users: InMemoryUserRepository) -> None:
    user = make_totvs_user("joao")
    await users.save(user)

    with pytest.raises(InvalidValueError, match="próprio TOTVS"):
        await ResetUserPasswordUseCase(users=users, hasher=fast_hasher()).execute(
            admin, user.id, temporary_password="provisoria-2"
        )


class TestUpdate:
    async def test_deactivates_and_promotes(self, users: InMemoryUserRepository) -> None:
        user = make_user("ana")
        await users.save(user)

        await UpdateUserUseCase(users).execute(admin, user.id, is_active=False, role=UserRole.ADMIN)

        assert not user.is_active
        assert user.is_admin

    async def test_approves_a_user_awaiting_access(self, users: InMemoryUserRepository) -> None:
        pending = make_totvs_user("joao", role=UserRole.PENDING)
        await users.save(pending)

        await UpdateUserUseCase(users).execute(admin, pending.id, role=UserRole.USER)

        assert not pending.is_pending

    @pytest.mark.parametrize(
        "change",
        [{"is_active": False}, {"role": UserRole.USER}, {"role": UserRole.PENDING}],
    )
    async def test_admins_cannot_lock_themselves_out(
        self, users: InMemoryUserRepository, change: dict[str, object]
    ) -> None:
        await users.save(admin)

        with pytest.raises(InvalidValueError, match="a si mesmo"):
            await UpdateUserUseCase(users).execute(admin, admin.id, **change)  # type: ignore[arg-type]

    async def test_unknown_user(self, users: InMemoryUserRepository) -> None:
        with pytest.raises(UserNotFoundError):
            await UpdateUserUseCase(users).execute(admin, UserId(uuid4()), is_active=True)


class TestUseTotvsLogin:
    async def test_switches_a_local_user_keeping_the_role(
        self, users: InMemoryUserRepository
    ) -> None:
        user = make_user("ana", role=UserRole.ADMIN)
        await users.save(user)

        await UseTotvsLoginUseCase(users).execute_as_system(username=" ANA ")

        assert (user.auth_source, user.password_hash) == (AuthSource.TOTVS, None)
        assert user.is_admin

    async def test_unknown_user(self, users: InMemoryUserRepository) -> None:
        with pytest.raises(UserNotFoundError):
            await UseTotvsLoginUseCase(users).execute_as_system(username="ninguem")
