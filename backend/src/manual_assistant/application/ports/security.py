from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from manual_assistant.domain.login_attempts import LoginAttempts
from manual_assistant.domain.session import Session


class PasswordHasher(Protocol):
    """Transforma senhas em hashes irreversíveis e confere senhas contra eles."""

    def hash(self, password: str) -> str: ...

    def verify(self, password: str, password_hash: str) -> bool: ...

    def needs_rehash(self, password_hash: str) -> bool:
        """True quando o hash usa parâmetros antigos e deve ser refeito no próximo login."""
        ...


@dataclass(frozen=True, slots=True)
class SessionToken:
    """O que vai no cookie. ``value`` só existe aqui: o banco guarda apenas o hash dele."""

    value: str
    expires_at: datetime


class SessionRepository(Protocol):
    """
    Raises (todos os métodos):
        ExternalServiceError: se o armazenamento falhar.
    """

    async def add(self, session: Session) -> None: ...

    async def get(self, token_hash: str) -> Session | None: ...

    async def touch(self, token_hash: str, last_seen_at: datetime) -> None:
        """Registra o último uso (renova o prazo de inatividade)."""
        ...

    async def delete(self, token_hash: str) -> None: ...

    async def delete_expired(self, *, last_seen_before: datetime, created_before: datetime) -> None:
        """Faxina: apaga as sessões paradas desde ``last_seen_before`` ou criadas antes de
        ``created_before``."""
        ...


class LoginAttemptRepository(Protocol):
    """
    Raises (todos os métodos):
        ExternalServiceError: se o armazenamento falhar.
    """

    async def get(self, username: str) -> LoginAttempts:
        """Tentativas do login já normalizado; sem registro, devolve um zerado."""
        ...

    async def save(self, attempts: LoginAttempts) -> None: ...

    async def clear(self, username: str) -> None: ...
