import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from manual_assistant.application.clock import Clock, utc_now
from manual_assistant.application.errors import AccountLockedError, InvalidCredentialsError
from manual_assistant.application.ports.security import PasswordHasher, SessionToken, TokenService
from manual_assistant.application.ports.user_repository import UserRepository
from manual_assistant.domain.user import User, normalize_username

DEFAULT_MAX_FAILED_ATTEMPTS = 5
DEFAULT_LOCKOUT = timedelta(minutes=15)


@dataclass(frozen=True, slots=True)
class AuthenticatedSession:
    user: User
    token: SessionToken


class AuthenticateUserUseCase:
    def __init__(
        self,
        *,
        users: UserRepository,
        hasher: PasswordHasher,
        tokens: TokenService,
        max_failed_attempts: int = DEFAULT_MAX_FAILED_ATTEMPTS,
        lockout: timedelta = DEFAULT_LOCKOUT,
        clock: Clock = utc_now,
    ) -> None:
        self._users = users
        self._hasher = hasher
        self._tokens = tokens
        self._max_failed_attempts = max_failed_attempts
        self._lockout = lockout
        self._clock = clock
        # Conferido quando o login não existe, para que a resposta demore o mesmo tempo
        # e não denuncie quais logins existem.
        self._dummy_hash = hasher.hash("senha-que-nunca-confere")

    async def execute(self, *, username: str, password: str) -> AuthenticatedSession:
        """
        Raises:
            InvalidCredentialsError: login inexistente, senha errada ou conta inativa.
            AccountLockedError: muitas tentativas erradas seguidas.
        """
        now = self._clock()
        user = await self._users.get_by_username(normalize_username(username))
        if user is None:
            self._hasher.verify(password, self._dummy_hash)
            raise InvalidCredentialsError()

        if user.is_locked(now):
            raise AccountLockedError(_minutes_left(user, now))

        if not self._hasher.verify(password, user.password_hash):
            user.record_failed_login(
                now, max_attempts=self._max_failed_attempts, lockout=self._lockout
            )
            await self._users.save(user)
            if user.is_locked(now):
                raise AccountLockedError(_minutes_left(user, now))
            raise InvalidCredentialsError()

        if not user.is_active:
            raise InvalidCredentialsError()

        if self._hasher.needs_rehash(user.password_hash):
            # Parâmetros de hash evoluem; o login é o único momento em que temos a senha.
            user.password_hash = self._hasher.hash(password)
        user.record_successful_login(now)
        await self._users.save(user)
        return AuthenticatedSession(user=user, token=self._tokens.issue(user.id))


def _minutes_left(user: User, now: datetime) -> int:
    locked_until = user.locked_until or now
    return max(1, math.ceil((locked_until - now).total_seconds() / 60))
