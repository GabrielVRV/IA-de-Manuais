import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from manual_assistant.application.clock import Clock, utc_now
from manual_assistant.application.errors import (
    AccountDisabledError,
    AccountLockedError,
    InvalidCredentialsError,
    PasswordExpiredError,
    PermissionDeniedError,
)
from manual_assistant.application.ports.credential_verifier import (
    CredentialStatus,
    CredentialVerifier,
)
from manual_assistant.application.ports.security import (
    LoginAttemptRepository,
    PasswordHasher,
    SessionToken,
)
from manual_assistant.application.ports.user_repository import UserRepository
from manual_assistant.application.sessions import SessionManager
from manual_assistant.domain.login_attempts import LoginAttempts
from manual_assistant.domain.user import User, is_valid_username, normalize_username

DEFAULT_MAX_FAILED_ATTEMPTS = 5
DEFAULT_LOCKOUT = timedelta(minutes=15)


@dataclass(frozen=True, slots=True)
class AuthenticatedSession:
    user: User
    token: SessionToken


@dataclass(frozen=True, slots=True)
class _Verification:
    valid: bool
    # Nome vindo do TOTVS, quando a senha foi conferida lá.
    totvs_display_name: str | None = None


class AuthenticateUserUseCase:
    """Login. Usuários locais têm a senha conferida aqui; os demais, no TOTVS.

    Um login do TOTVS que ainda não existe aqui é cadastrado como "aguardando liberação".
    """

    def __init__(
        self,
        *,
        users: UserRepository,
        attempts: LoginAttemptRepository,
        hasher: PasswordHasher,
        sessions: SessionManager,
        totvs: CredentialVerifier | None = None,
        max_failed_attempts: int = DEFAULT_MAX_FAILED_ATTEMPTS,
        lockout: timedelta = DEFAULT_LOCKOUT,
        clock: Clock = utc_now,
    ) -> None:
        self._users = users
        self._attempts = attempts
        self._hasher = hasher
        self._sessions = sessions
        self._totvs = totvs
        self._max_failed_attempts = max_failed_attempts
        self._lockout = lockout
        self._clock = clock
        # Conferido quando não há onde validar o login, para que a resposta demore o
        # mesmo tempo e não denuncie quais logins locais existem.
        self._dummy_hash = hasher.hash("senha-que-nunca-confere")

    async def execute(self, *, username: str, password: str) -> AuthenticatedSession:
        """
        Raises:
            InvalidCredentialsError: login inexistente ou senha errada.
            AccountLockedError: muitas tentativas erradas seguidas.
            PasswordExpiredError: senha certa, mas vencida no TOTVS.
            AccountDisabledError: senha certa, mas usuário desativado.
            ExternalServiceError: TOTVS fora do ar (não conta como tentativa errada).
        """
        now = self._clock()
        name = normalize_username(username)
        # O bloqueio vem antes do TOTVS: ninguém consegue bloquear a conta de um colega no
        # Datasul errando a senha aqui de propósito.
        attempts = await self._attempts.get(name)
        if attempts.is_locked(now):
            raise AccountLockedError(_minutes_left(attempts, now))

        user = await self._users.get_by_username(name)
        verification = await self._verify(user, name, password)
        if not verification.valid:
            await self._record_failure(attempts, now)
            raise InvalidCredentialsError()
        if attempts.failed_count or attempts.locked_until:
            await self._attempts.clear(name)

        if user is None:
            user = self._provision(name, verification.totvs_display_name or name, now)
        elif verification.totvs_display_name:
            user.sync_display_name(verification.totvs_display_name)

        if not user.is_active:
            raise AccountDisabledError()
        if user.password_hash is not None and self._hasher.needs_rehash(user.password_hash):
            # Parâmetros de hash evoluem; o login é o único momento em que temos a senha.
            user.password_hash = self._hasher.hash(password)
        user.record_successful_login(now)
        await self._users.save(user)
        return AuthenticatedSession(user=user, token=await self._sessions.start(user.id))

    async def _verify(self, user: User | None, name: str, password: str) -> _Verification:
        if user is not None and user.password_hash is not None:  # usuário local
            return _Verification(valid=self._hasher.verify(password, user.password_hash))
        if self._totvs is None:  # login pelo TOTVS desligado
            self._hasher.verify(password, self._dummy_hash)
            return _Verification(valid=False)

        check = await self._totvs.verify(name, password)
        if check.status is CredentialStatus.EXPIRED:
            await self._attempts.clear(name)  # a senha conferiu: não é força bruta
            raise PasswordExpiredError()
        return _Verification(
            valid=check.status is CredentialStatus.VALID, totvs_display_name=check.display_name
        )

    async def _record_failure(self, attempts: LoginAttempts, now: datetime) -> None:
        attempts.record_failure(now, max_attempts=self._max_failed_attempts, lockout=self._lockout)
        await self._attempts.save(attempts)
        if attempts.is_locked(now):
            raise AccountLockedError(_minutes_left(attempts, now))

    @staticmethod
    def _provision(name: str, display_name: str, now: datetime) -> User:
        if not is_valid_username(name):
            raise PermissionDeniedError(
                "Seu login do TOTVS não pode ser usado neste sistema. "
                "Peça a um administrador um usuário local."
            )
        return User.provision_from_totvs(username=name, display_name=display_name, now=now)


def _minutes_left(attempts: LoginAttempts, now: datetime) -> int:
    locked_until = attempts.locked_until or now
    return max(1, math.ceil((locked_until - now).total_seconds() / 60))
