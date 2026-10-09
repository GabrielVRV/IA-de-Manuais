from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class CredentialStatus(StrEnum):
    VALID = "valid"
    INVALID = "invalid"  # usuário inexistente ou senha errada (o sistema externo não diz qual)
    EXPIRED = "expired"  # senha certa, mas vencida


@dataclass(frozen=True, slots=True)
class CredentialCheck:
    status: CredentialStatus
    # Nome cadastrado no sistema externo; só vem quando a senha confere.
    display_name: str | None = None


class CredentialVerifier(Protocol):
    """Confere usuário e senha num sistema externo (o TOTVS), sem que a senha fique aqui."""

    async def verify(self, username: str, password: str) -> CredentialCheck:
        """
        Raises:
            ExternalServiceError: sistema fora do ar, lento demais ou resposta inesperada.
        """
        ...
