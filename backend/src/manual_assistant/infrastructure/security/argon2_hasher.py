import argon2
from argon2.exceptions import InvalidHashError, VerificationError


class Argon2PasswordHasher:
    """Argon2id: algoritmo recomendado pela OWASP para guardar senhas.

    Os parâmetros padrão da biblioteca (64 MiB, 3 iterações) tornam ataques de força
    bruta caros. Os testes usam parâmetros mínimos para rodar rápido.
    """

    def __init__(self, *, time_cost: int = 3, memory_cost_kib: int = 65536) -> None:
        self._hasher = argon2.PasswordHasher(time_cost=time_cost, memory_cost=memory_cost_kib)

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (VerificationError, InvalidHashError):
            return False

    def needs_rehash(self, password_hash: str) -> bool:
        return self._hasher.check_needs_rehash(password_hash)
