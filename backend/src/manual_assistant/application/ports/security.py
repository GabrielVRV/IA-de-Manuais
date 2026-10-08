from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from manual_assistant.domain.user import UserId


class PasswordHasher(Protocol):
    """Transforma senhas em hashes irreversíveis e confere senhas contra eles."""

    def hash(self, password: str) -> str: ...

    def verify(self, password: str, password_hash: str) -> bool: ...

    def needs_rehash(self, password_hash: str) -> bool:
        """True quando o hash usa parâmetros antigos e deve ser refeito no próximo login."""
        ...


@dataclass(frozen=True, slots=True)
class SessionToken:
    value: str
    expires_at: datetime


class TokenService(Protocol):
    """Emite e confere tokens de sessão.

    O token identifica só o usuário: perfil e status são lidos do banco a cada
    requisição, então desativar alguém tem efeito imediato.
    """

    def issue(self, user_id: UserId) -> SessionToken: ...

    def verify(self, token: str) -> UserId:
        """
        Raises:
            NotAuthenticatedError: se o token for inválido ou estiver expirado.
        """
        ...
