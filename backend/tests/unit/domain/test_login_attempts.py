from datetime import timedelta

from manual_assistant.domain.login_attempts import LoginAttempts
from tests.factories import FIXED_NOW

LOCKOUT = timedelta(minutes=15)


def test_locks_after_the_maximum_number_of_failures() -> None:
    attempts = LoginAttempts(username="maria")
    for _ in range(4):
        attempts.record_failure(FIXED_NOW, max_attempts=5, lockout=LOCKOUT)
        assert not attempts.is_locked(FIXED_NOW)

    attempts.record_failure(FIXED_NOW, max_attempts=5, lockout=LOCKOUT)

    assert attempts.is_locked(FIXED_NOW)
    assert not attempts.is_locked(FIXED_NOW + LOCKOUT)
    assert attempts.failed_count == 0  # depois do bloqueio, a contagem recomeça
