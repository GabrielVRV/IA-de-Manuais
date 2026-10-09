from datetime import timedelta
from uuid import uuid4

import pytest

from manual_assistant.application.errors import (
    AccountDisabledError,
    AccountLockedError,
    ExternalServiceError,
    InvalidCredentialsError,
    NotAuthenticatedError,
    PasswordExpiredError,
    PermissionDeniedError,
)
from manual_assistant.application.sessions import TOUCH_INTERVAL, hash_token
from manual_assistant.application.use_cases.authenticate_user import (
    AuthenticatedSession,
    AuthenticateUserUseCase,
)
from manual_assistant.application.use_cases.change_password import ChangePasswordUseCase
from manual_assistant.application.use_cases.resolve_session import (
    LogoutUseCase,
    ResolveSessionUseCase,
)
from manual_assistant.domain.errors import InvalidValueError
from manual_assistant.domain.user import AuthSource, User, UserId, UserRole
from manual_assistant.infrastructure.security.argon2_hasher import Argon2PasswordHasher
from tests.factories import FIXED_NOW
from tests.fakes import (
    FakeTotvs,
    InMemoryLoginAttemptRepository,
    InMemorySessionRepository,
    InMemoryUserRepository,
)
from tests.security import (
    DEFAULT_PASSWORD,
    SESSION_POLICY,
    fast_hasher,
    make_totvs_user,
    make_user,
    session_manager,
)

pytestmark = pytest.mark.anyio


class SpyHasher(Argon2PasswordHasher):
    def __init__(self) -> None:
        super().__init__(time_cost=1, memory_cost_kib=64)
        self.verifications = 0

    def verify(self, password: str, password_hash: str) -> bool:
        self.verifications += 1
        return super().verify(password, password_hash)


class Context:
    def __init__(self, *, with_totvs: bool = True) -> None:
        self.users = InMemoryUserRepository()
        self.attempts = InMemoryLoginAttemptRepository()
        self.sessions = InMemorySessionRepository()
        self.hasher = SpyHasher()
        self.totvs = FakeTotvs()
        self.now = FIXED_NOW
        self.session_manager = session_manager(self.sessions, clock=lambda: self.now)
        self.authenticate = AuthenticateUserUseCase(
            users=self.users,
            attempts=self.attempts,
            hasher=self.hasher,
            sessions=self.session_manager,
            totvs=self.totvs if with_totvs else None,
            max_failed_attempts=3,
            lockout=timedelta(minutes=10),
            clock=lambda: self.now,
        )

    async def add(self, user: User) -> User:
        await self.users.save(user)
        return user

    async def login(
        self, username: str = "maria", password: str = DEFAULT_PASSWORD
    ) -> AuthenticatedSession:
        return await self.authenticate.execute(username=username, password=password)


@pytest.fixture
def ctx() -> Context:
    return Context()


class TestLocalUsers:
    async def test_issues_a_session_for_valid_credentials(self, ctx: Context) -> None:
        user = await ctx.add(make_user("maria"))

        session = await ctx.login(" MARIA ")

        assert session.user is user
        assert session.token.expires_at == FIXED_NOW + SESSION_POLICY.max_age
        assert await ctx.session_manager.resolve(session.token.value) == user.id
        assert user.last_login_at == FIXED_NOW

    async def test_never_asks_the_totvs(self, ctx: Context) -> None:
        await ctx.add(make_user("maria"))
        ctx.totvs.add("maria", "senha-do-totvs")

        with pytest.raises(InvalidCredentialsError):
            await ctx.login(password="senha-do-totvs")

        assert ctx.totvs.calls == []

    async def test_wrong_password_is_counted(self, ctx: Context) -> None:
        await ctx.add(make_user("maria"))

        with pytest.raises(InvalidCredentialsError, match="Usuário ou senha inválidos"):
            await ctx.login(password="errada-123")

        assert (await ctx.attempts.get("maria")).failed_count == 1

    async def test_a_successful_login_clears_the_failures(self, ctx: Context) -> None:
        await ctx.add(make_user("maria"))
        with pytest.raises(InvalidCredentialsError):
            await ctx.login(password="errada-123")

        await ctx.login()

        assert ctx.attempts.attempts == {}

    async def test_inactive_accounts_are_told_after_the_password_matches(
        self, ctx: Context
    ) -> None:
        user = await ctx.add(make_user("maria"))
        user.deactivate()

        with pytest.raises(InvalidCredentialsError):
            await ctx.login(password="errada-123")
        with pytest.raises(AccountDisabledError, match="desativado"):
            await ctx.login()

    async def test_rehashes_passwords_created_with_old_parameters(self, ctx: Context) -> None:
        weak = Argon2PasswordHasher(time_cost=1, memory_cost_kib=32)
        user = await ctx.add(make_user("maria", hasher=weak))
        old_hash = user.password_hash

        await ctx.login()

        assert user.password_hash != old_hash
        assert user.password_hash is not None
        assert ctx.hasher.verify(DEFAULT_PASSWORD, user.password_hash)


class TestTotvsUsers:
    async def test_first_login_registers_the_user_awaiting_approval(self, ctx: Context) -> None:
        ctx.totvs.add("joao", "senha-do-totvs", name="João da Silva")

        session = await ctx.login("JOAO", "senha-do-totvs")

        user = session.user
        assert (user.username, user.display_name) == ("joao", "João da Silva")
        assert (user.role, user.auth_source) == (UserRole.PENDING, AuthSource.TOTVS)
        assert user.password_hash is None
        assert not user.must_change_password
        assert await ctx.users.get_by_username("joao") is user
        assert ctx.totvs.calls == ["joao"]

    async def test_later_logins_keep_the_role_and_follow_the_totvs_name(self, ctx: Context) -> None:
        user = await ctx.add(make_totvs_user("joao", role=UserRole.ADMIN))
        ctx.totvs.add("joao", "senha-do-totvs", name="João Novo Nome")

        session = await ctx.login("joao", "senha-do-totvs")

        assert session.user is user
        assert user.is_admin
        assert user.display_name == "João Novo Nome"

    async def test_wrong_password_creates_nobody_and_is_counted(self, ctx: Context) -> None:
        ctx.totvs.add("joao", "senha-do-totvs")

        with pytest.raises(InvalidCredentialsError):
            await ctx.login("joao", "errada")

        assert await ctx.users.get_by_username("joao") is None
        assert (await ctx.attempts.get("joao")).failed_count == 1

    async def test_the_lockout_is_checked_before_reaching_the_totvs(self, ctx: Context) -> None:
        """Ninguém consegue bloquear a conta de um colega no Datasul errando aqui."""
        ctx.totvs.add("joao", "senha-do-totvs")
        for _ in range(2):
            with pytest.raises(InvalidCredentialsError):
                await ctx.login("joao", "errada")
        with pytest.raises(AccountLockedError, match="10 minuto"):
            await ctx.login("joao", "errada")

        with pytest.raises(AccountLockedError):
            await ctx.login("joao", "senha-do-totvs")  # nem a senha certa entra
        assert len(ctx.totvs.calls) == 3

        ctx.now += timedelta(minutes=10)
        assert (await ctx.login("joao", "senha-do-totvs")).user.username == "joao"

    async def test_expired_password(self, ctx: Context) -> None:
        ctx.totvs.add("joao", "senha-do-totvs")
        ctx.totvs.expired.add("joao")

        with pytest.raises(PasswordExpiredError, match="Redefina-a no TOTVS"):
            await ctx.login("joao", "senha-do-totvs")

        assert await ctx.users.get_by_username("joao") is None
        assert ctx.attempts.attempts == {}

    async def test_totvs_outage_is_not_a_failed_attempt(self, ctx: Context) -> None:
        ctx.totvs.error = ExternalServiceError("O TOTVS não respondeu")

        with pytest.raises(ExternalServiceError):
            await ctx.login("joao", "qualquer")

        assert ctx.attempts.attempts == {}

    async def test_deactivated_users_stay_out(self, ctx: Context) -> None:
        user = await ctx.add(make_totvs_user("joao"))
        user.deactivate()
        ctx.totvs.add("joao", "senha-do-totvs")

        with pytest.raises(AccountDisabledError):
            await ctx.login("joao", "senha-do-totvs")

    async def test_totvs_logins_outside_our_format_are_explained(self, ctx: Context) -> None:
        ctx.totvs.add("jo", "senha-do-totvs")

        with pytest.raises(PermissionDeniedError, match="usuário local"):
            await ctx.login("jo", "senha-do-totvs")

    async def test_without_totvs_only_local_users_get_in(self) -> None:
        ctx = Context(with_totvs=False)

        with pytest.raises(InvalidCredentialsError):
            await ctx.login("joao", "qualquer")

        # Conferiu o hash de referência: o tempo de resposta não denuncia o login.
        assert ctx.hasher.verifications == 1


class TestSessions:
    async def test_resolves_the_user_of_a_session(self, ctx: Context) -> None:
        user = await ctx.add(make_user())
        token = (await ctx.login()).token.value

        resolved = await ResolveSessionUseCase(
            users=ctx.users, sessions=ctx.session_manager
        ).execute(token)

        assert resolved is user

    async def test_only_the_token_hash_is_stored(self, ctx: Context) -> None:
        await ctx.add(make_user())

        token = (await ctx.login()).token.value

        assert list(ctx.sessions.sessions) == [hash_token(token)]
        assert hash_token(token) != token

    async def test_expires_after_a_week_without_use(self, ctx: Context) -> None:
        await ctx.add(make_user())
        token = (await ctx.login()).token.value

        ctx.now += timedelta(days=6)
        await ctx.session_manager.resolve(token)  # o uso renova o prazo
        ctx.now += timedelta(days=6)
        await ctx.session_manager.resolve(token)

        ctx.now += timedelta(days=7)
        with pytest.raises(NotAuthenticatedError, match="expirou"):
            await ctx.session_manager.resolve(token)
        assert ctx.sessions.sessions == {}

    async def test_expires_after_30_days_even_with_daily_use(self, ctx: Context) -> None:
        await ctx.add(make_user())
        token = (await ctx.login()).token.value

        for _ in range(29):
            ctx.now += timedelta(days=1)
            await ctx.session_manager.resolve(token)

        ctx.now += timedelta(days=1)
        with pytest.raises(NotAuthenticatedError):
            await ctx.session_manager.resolve(token)

    async def test_records_the_last_use_at_most_every_few_minutes(self, ctx: Context) -> None:
        await ctx.add(make_user())
        token = (await ctx.login()).token.value

        await ctx.session_manager.resolve(token)
        ctx.now += TOUCH_INTERVAL
        await ctx.session_manager.resolve(token)

        assert ctx.sessions.touches == 1

    async def test_logins_clean_up_expired_sessions(self, ctx: Context) -> None:
        await ctx.add(make_user())
        await ctx.login()

        ctx.now += timedelta(days=8)
        await ctx.login()

        assert len(ctx.sessions.sessions) == 1

    async def test_logout_ends_the_session(self, ctx: Context) -> None:
        await ctx.add(make_user())
        token = (await ctx.login()).token.value

        await LogoutUseCase(ctx.session_manager).execute(token)

        with pytest.raises(NotAuthenticatedError):
            await ctx.session_manager.resolve(token)

    @pytest.mark.parametrize("situation", ["removido", "desativado"])
    async def test_ends_sessions_of_removed_or_inactive_users(self, situation: str) -> None:
        users, sessions = InMemoryUserRepository(), session_manager()
        user = make_user()
        if situation == "desativado":
            user.deactivate()
            await users.save(user)
        token = await sessions.start(user.id if situation == "desativado" else UserId(uuid4()))

        with pytest.raises(NotAuthenticatedError, match="encerrada"):
            await ResolveSessionUseCase(users=users, sessions=sessions).execute(token.value)

    async def test_rejects_unknown_tokens(self) -> None:
        with pytest.raises(NotAuthenticatedError):
            await session_manager().resolve("token-inventado")


class TestChangePassword:
    async def test_changes_the_password_and_clears_the_pending_change(self) -> None:
        users, hasher = InMemoryUserRepository(), fast_hasher()
        user = make_user(must_change_password=True)

        await ChangePasswordUseCase(users=users, hasher=hasher).execute(
            user, current_password=DEFAULT_PASSWORD, new_password="nova-senha-forte"
        )

        assert user.password_hash is not None
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

    async def test_totvs_users_change_it_in_the_totvs(self) -> None:
        use_case = ChangePasswordUseCase(users=InMemoryUserRepository(), hasher=fast_hasher())

        with pytest.raises(InvalidValueError, match="próprio TOTVS"):
            await use_case.execute(
                make_totvs_user(), current_password="x", new_password="nova-senha-forte"
            )
