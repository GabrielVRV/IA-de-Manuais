from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class CredentialStatus(StrEnum):
    VALID = "valid"
    INVALID = "invalid"  # usuário inexistente ou senha errada (o sistema externo não diz qual)
    EXPIRED = "expired"  # senha certa, mas vencida (ou com troca obrigatória)
    BLOCKED = "blocked"  # conta desativada, expirada ou bloqueada no sistema externo
    NOT_ALLOWED = "not_allowed"  # senha certa, mas fora do grupo que libera este sistema


@dataclass(frozen=True, slots=True)
class CredentialCheck:
    status: CredentialStatus
    # Nome cadastrado no sistema externo; só vem quando a senha confere.
    display_name: str | None = None


class CredentialVerifier(Protocol):
    """Confere usuário e senha num sistema externo (o AD), sem que a senha fique aqui."""

    async def verify(self, username: str, password: str) -> CredentialCheck:
        """
        Raises:
            ExternalServiceError: sistema fora do ar, lento demais ou resposta inesperada.
        """
        ...
