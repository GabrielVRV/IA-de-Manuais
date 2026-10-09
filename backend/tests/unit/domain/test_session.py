from datetime import timedelta
from uuid import uuid4

from manual_assistant.domain.session import Session, SessionPolicy
from manual_assistant.domain.user import UserId
from tests.factories import FIXED_NOW

POLICY = SessionPolicy(idle_timeout=timedelta(days=7), max_age=timedelta(days=30))


def session(*, last_seen_days: int) -> Session:
    return Session(
        token_hash="h",
        user_id=UserId(uuid4()),
        created_at=FIXED_NOW,
        last_seen_at=FIXED_NOW + timedelta(days=last_seen_days),
    )


def test_expires_after_the_idle_timeout() -> None:
    recent = session(last_seen_days=2)

    assert recent.expires_at(POLICY) == FIXED_NOW + timedelta(days=9)
    assert not recent.is_expired(FIXED_NOW + timedelta(days=8), POLICY)
    assert recent.is_expired(FIXED_NOW + timedelta(days=9), POLICY)


def test_never_outlives_the_maximum_age() -> None:
    used_yesterday = session(last_seen_days=29)

    assert used_yesterday.expires_at(POLICY) == FIXED_NOW + timedelta(days=30)
