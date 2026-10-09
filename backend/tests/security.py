"""Peças de segurança rápidas para testes (o Argon2 de produção leva ~50 ms por hash)."""

from datetime import timedelta

from manual_assistant.application.clock import Clock, utc_now
from manual_assistant.application.sessions import SessionManager
from manual_assistant.domain.session import SessionPolicy
from manual_assistant.domain.user import User, UserRole
from manual_assistant.infrastructure.security.argon2_hasher import Argon2PasswordHasher
from tests.factories import FIXED_NOW
from tests.fakes import InMemorySessionRepository

DEFAULT_PASSWORD = "senha-forte-123"
SESSION_POLICY = SessionPolicy(idle_timeout=timedelta(days=7), max_age=timedelta(days=30))


def fast_hasher() -> Argon2PasswordHasher:
    return Argon2PasswordHasher(time_cost=1, memory_cost_kib=64)


def session_manager(
    repository: InMemorySessionRepository | None = None, *, clock: Clock = utc_now
) -> SessionManager:
    return SessionManager(
        repository if repository is not None else InMemorySessionRepository(),
        policy=SESSION_POLICY,
        clock=clock,
    )


def make_user(
    username: str = "maria",
    *,
    role: UserRole = UserRole.USER,
    password: str = DEFAULT_PASSWORD,
    must_change_password: bool = False,
    hasher: Argon2PasswordHasher | None = None,
) -> User:
    user = User.register(
        username=username,
        display_name=username.title(),
        role=role,
        password_hash=(hasher or fast_hasher()).hash(password),
        now=FIXED_NOW,
    )
    user.must_change_password = must_change_password
    return user


def make_totvs_user(username: str = "joao", *, role: UserRole = UserRole.USER) -> User:
    user = User.provision_from_totvs(
        username=username, display_name=username.title(), now=FIXED_NOW
    )
    user.role = role
    return user
