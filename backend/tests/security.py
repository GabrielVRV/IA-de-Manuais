"""Peças de segurança rápidas para testes (o Argon2 de produção leva ~50 ms por hash)."""

from datetime import timedelta

from manual_assistant.domain.user import User, UserRole
from manual_assistant.infrastructure.security.argon2_hasher import Argon2PasswordHasher
from manual_assistant.infrastructure.security.jwt_tokens import JwtTokenService
from tests.factories import FIXED_NOW

TEST_SECRET = "segredo-de-teste-com-mais-de-32-caracteres"
DEFAULT_PASSWORD = "senha-forte-123"


def fast_hasher() -> Argon2PasswordHasher:
    return Argon2PasswordHasher(time_cost=1, memory_cost_kib=64)


def token_service() -> JwtTokenService:
    return JwtTokenService(TEST_SECRET, ttl=timedelta(hours=1))


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
