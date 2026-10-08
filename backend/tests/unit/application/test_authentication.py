from datetime import timedelta
from uuid import uuid4

import pytest

from manual_assistant.application.errors import (
    AccountLockedError,
    InvalidCredentialsError,
    NotAuthenticatedError,
)
from manual_assistant.application.use_cases.authenticate_user import AuthenticateUserUseCase
from manual_assistant.application.use_cases.change_password import ChangePasswordUseCase
from manual_assistant.application.use_cases.resolve_session import ResolveSessionUseCase
from manual_assistant.domain.errors import InvalidValueError
from manual_assistant.domain.user import User, UserId
from manual_assistant.infrastructure.security.argon2_hasher import Argon2PasswordHasher
from tests.factories import FIXED_NOW
from tests.fakes import InMemoryUserRepository
from tests.security import DEFAULT_PASSWORD, fast_hasher, make_user, token_service

pytestmark = pytest.mark.anyio


class SpyHasher(Argon2PasswordHasher):
    def __init__(self) -> None:
        super().__init__(time_cost=1, memory_cost_kib=64)
        self.verifications = 0

    def verify(self, password: str, password_hash: str) -> bool:
        self.verifications += 1
        return super().verify(password, password_hash)


class Context:
    def __init__(self) -> None:
        self.users = InMemoryUserRepository()
        self.hasher = SpyHasher()
        self.tokens = token_service()
        self.now = FIXED_NOW
        self.authenticate = AuthenticateUserUseCase(
            users=self.users,
            hasher=self.hasher,
            tokens=self.tokens,
            max_failed_attempts=3,
            lockout=timedelta(minutes=10),
            clock=lambda: self.now,
        )

    async def add(self, user: User) -> User:
        await self.users.save(user)
        return user

    async def login(self, username: str = "maria", password: str = DEFAULT_PASSWORD) -> User:
        return (await self.authenticate.execute(username=username, password=password)).user


@pytest.fixture
def ctx() -> Context:
    return Context()


class TestAuthenticate:
    async def test_issues_a_session_for_valid_credentials(self, ctx: Context) -> None:
        user = await ctx.add(make_user("maria"))

        session = await ctx.authenticate.execute(username=" MARIA ", password=DEFAULT_PASSWORD)

        assert session.user is user
        assert ctx.tokens.verify(session.token.value) == user.id
        assert user.last_login_at == FIXED_NOW

    async def test_unknown_login_gets_the_same_error_and_still_checks_a_hash(
        self, ctx: Context
    ) -> None:
        with pytest.raises(InvalidCredentialsError, match="Usuário ou senha inválidos"):
            await ctx.login("ninguem")

        # Conferiu o hash de referência: o tempo de resposta não denuncia o login.
        assert ctx.hasher.verifications == 1

    async def test_wrong_password_is_counted(self, ctx: Context) -> None:
        user = await ctx.add(make_user("maria"))

        with pytest.raises(InvalidCredentialsError):
            await ctx.login(password="errada-123")

        assert user.failed_login_attempts == 1

    async def test_locks_the_account_after_repeated_failures(self, ctx: Context) -> None:
        await ctx.add(make_user("maria"))
        for _ in range(2):
            with pytest.raises(InvalidCredentialsError):
                await ctx.login(password="errada-123")

        with pytest.raises(AccountLockedError, match="10 minuto"):
            await ctx.login(password="errada-123")
        with pytest.raises(AccountLockedError):
            await ctx.login()  # nem a senha certa entra durante o bloqueio

        ctx.now += timedelta(minutes=10)
        assert (await ctx.login()).username == "maria"

    async def test_inactive_accounts_cannot_log_in(self, ctx: Context) -> None:
        user = await ctx.add(make_user("maria"))
        user.deactivate()

        with pytest.raises(InvalidCredentialsError):
            await ctx.login()

    async def test_rehashes_passwords_created_with_old_parameters(self, ctx: Context) -> None:
        weak = Argon2PasswordHasher(time_cost=1, memory_cost_kib=32)
        user = await ctx.add(make_user("maria", hasher=weak))
        old_hash = user.password_hash

        await ctx.login()

        assert user.password_hash != old_hash
        assert ctx.hasher.verify(DEFAULT_PASSWORD, user.password_hash)


class TestResolveSession:
    async def test_returns_the_user_of_a_valid_token(self) -> None:
        users, tokens = InMemoryUserRepository(), token_service()
        user = make_user()
        await users.save(user)

        resolved = await ResolveSessionUseCase(users=users, tokens=tokens).execute(
            tokens.issue(user.id).value
        )

        assert resolved is user

    @pytest.mark.parametrize("situation", ["removido", "desativado"])
    async def test_ends_sessions_of_removed_or_inactive_users(self, situation: str) -> None:
        users, tokens = InMemoryUserRepository(), token_service()
        user = make_user()
        if situation == "desativado":
            user.deactivate()
            await users.save(user)
        token = tokens.issue(user.id if situation == "desativado" else UserId(uuid4())).value

        with pytest.raises(NotAuthenticatedError, match="encerrada"):
            await ResolveSessionUseCase(users=users, tokens=tokens).execute(token)


class TestChangePassword:
    async def test_changes_the_password_and_clears_the_pending_change(self) -> None:
        users, hasher = InMemoryUserRepository(), fast_hasher()
        user = make_user(must_change_password=True)

        await ChangePasswordUseCase(users=users, hasher=hasher).execute(
            user, current_password=DEFAULT_PASSWORD, new_password="nova-senha-forte"
        )

        assert hasher.verify("nova-senha-forte", user.password_hash)
        assert not user.must_change_password

    @pytest.mark.parametrize(
        ("current", "new", "message"),
        [
            ("errada-123", "nova-senha-forte", "atual está incorreta"),
            (DEFAULT_PASSWORD, DEFAULT_PASSWORD, "diferente da atual"),
            (DEFAULT_PASSWORD, "curta", "ao menos 8"),
        ],
    )
    async def test_rejects_invalid_changes(self, current: str, new: str, message: str) -> None:
        use_case = ChangePasswordUseCase(users=InMemoryUserRepository(), hasher=fast_hasher())

        with pytest.raises(InvalidValueError, match=message):
            await use_case.execute(make_user(), current_password=current, new_password=new)
