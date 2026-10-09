from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(kw_only=True, slots=True)
class LoginAttempts:
    """Erros de senha seguidos de um login digitado, existindo ele no cadastro ou não.

    Fica fora do usuário porque quem ainda não entrou pelo TOTVS não tem cadastro, e
    precisa ser barrado antes de chegar ao Datasul.
    """

    username: str
    failed_count: int = 0
    locked_until: datetime | None = None

    def is_locked(self, now: datetime) -> bool:
        return self.locked_until is not None and now < self.locked_until

    def record_failure(self, now: datetime, *, max_attempts: int, lockout: timedelta) -> None:
        """Após ``max_attempts`` erros seguidos, bloqueia por ``lockout`` (contra força bruta)."""
        self.failed_count += 1
        if self.failed_count >= max_attempts:
            self.locked_until = now + lockout
            self.failed_count = 0
