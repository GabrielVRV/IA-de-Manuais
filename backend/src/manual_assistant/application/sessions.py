import hashlib
import secrets
from datetime import timedelta

from manual_assistant.application.clock import Clock, utc_now
from manual_assistant.application.errors import NotAuthenticatedError
from manual_assistant.application.ports.security import SessionRepository, SessionToken
from manual_assistant.domain.session import Session, SessionPolicy
from manual_assistant.domain.user import UserId

# O último uso é gravado no máximo uma vez nesse intervalo, e não a cada requisição.
TOUCH_INTERVAL = timedelta(minutes=5)
_TOKEN_BYTES = 32  # 256 bits: impossível de adivinhar


def hash_token(token: str) -> str:
    """O banco guarda só o hash: um vazamento da tabela não dá sessões a ninguém."""
    return hashlib.sha256(token.encode()).hexdigest()


class SessionManager:
    """Abre, confere e encerra sessões guardadas no banco."""

    def __init__(
        self, repository: SessionRepository, *, policy: SessionPolicy, clock: Clock = utc_now
    ) -> None:
        self._repository = repository
        self._policy = policy
        self._clock = clock

    async def start(self, user_id: UserId) -> SessionToken:
        now = self._clock()
        await self._repository.delete_expired(
            last_seen_before=now - self._policy.idle_timeout,
            created_before=now - self._policy.max_age,
        )
        token = secrets.token_urlsafe(_TOKEN_BYTES)
        await self._repository.add(
            Session(token_hash=hash_token(token), user_id=user_id, created_at=now, last_seen_at=now)
        )
        # O cookie vale até o prazo absoluto; a inatividade é conferida aqui no servidor.
        return SessionToken(value=token, expires_at=now + self._policy.max_age)

    async def resolve(self, token: str) -> UserId:
        """
        Raises:
            NotAuthenticatedError: sessão inexistente, encerrada ou expirada.
        """
        token_hash = hash_token(token)
        session = await self._repository.get(token_hash)
        now = self._clock()
        if session is None or session.is_expired(now, self._policy):
            if session is not None:
                await self._repository.delete(token_hash)
            raise NotAuthenticatedError("Sua sessão expirou ou é inválida. Faça login novamente.")
        if now - session.last_seen_at >= TOUCH_INTERVAL:
            await self._repository.touch(token_hash, now)
        return session.user_id

    async def end(self, token: str) -> None:
        await self._repository.delete(hash_token(token))
