from dataclasses import dataclass
from datetime import datetime, timedelta

from manual_assistant.domain.user import UserId


@dataclass(frozen=True, slots=True)
class SessionPolicy:
    """Quanto tempo uma sessão vale: cai por inatividade ou pelo prazo absoluto."""

    idle_timeout: timedelta
    max_age: timedelta


@dataclass(kw_only=True, slots=True)
class Session:
    # SHA-256 do token do cookie: quem lê o banco não consegue montar um cookie válido.
    token_hash: str
    user_id: UserId
    created_at: datetime
    last_seen_at: datetime

    def expires_at(self, policy: SessionPolicy) -> datetime:
        return min(self.last_seen_at + policy.idle_timeout, self.created_at + policy.max_age)

    def is_expired(self, now: datetime, policy: SessionPolicy) -> bool:
        return now >= self.expires_at(policy)
