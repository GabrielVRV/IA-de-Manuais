from datetime import datetime, timedelta

import pytest

from manual_assistant.domain.errors import InvalidValueError
from manual_assistant.domain.user import User, UserRole, normalize_username, validate_password
from tests.factories import FIXED_NOW
from tests.security import make_user

LOCKOUT = timedelta(minutes=15)


def register(username: str = "maria.silva", display_name: str = "Maria") -> User:
    return User.register(
        username=username,
        display_name=display_name,
        role=UserRole.USER,
        password_hash="hash",
        now=FIXED_NOW,
    )


class TestRegistration:
    def test_normalizes_the_login_and_requires_a_password_change(self) -> None:
        user = register("  Maria.Silva ")

        assert user.username == "maria.silva"
        assert user.must_change_password
        assert user.is_active
        assert not user.is_admin

    @pytest.mark.parametrize("username", ["ab", "maria silva", "-maria", "maria@empresa", "x" * 51])
    def test_rejects_invalid_logins(self, username: str) -> None:
        with pytest.raises(InvalidValueError, match="login"):
            register(username)

    def test_rejects_blank_names_and_naive_dates(self) -> None:
        with pytest.raises(InvalidValueError):
            register(display_name="  ")
        with pytest.raises(InvalidValueError, match="fuso"):
            User.register(
                username="maria",
                display_name="Maria",
                role=UserRole.USER,
                password_hash="h",
                now=datetime(2026, 1, 1),  # noqa: DTZ001
            )


@pytest.mark.parametrize(
    ("password", "message"),
    [("curta", "ao menos 8"), ("x" * 129, "no máximo"), ("Maria.Silva", "igual ao login")],
)
def test_password_policy(password: str, message: str) -> None:
    with pytest.raises(InvalidValueError, match=message):
        validate_password(password, username="maria.silva")


def test_accepts_a_long_passphrase() -> None:
    validate_password("cavalo bateria grampo correto", username="maria")


def test_logins_are_case_insensitive() -> None:
    assert normalize_username(" GaBriel ") == "gabriel"


class TestLockout:
    def test_locks_after_the_maximum_number_of_failures(self) -> None:
        user = make_user()
        for _ in range(4):
            user.record_failed_login(FIXED_NOW, max_attempts=5, lockout=LOCKOUT)
            assert not user.is_locked(FIXED_NOW)

        user.record_failed_login(FIXED_NOW, max_attempts=5, lockout=LOCKOUT)

        assert user.is_locked(FIXED_NOW)
        assert not user.is_locked(FIXED_NOW + LOCKOUT)

    def test_successful_login_clears_failures(self) -> None:
        user = make_user()
        user.record_failed_login(FIXED_NOW, max_attempts=5, lockout=LOCKOUT)

        user.record_successful_login(FIXED_NOW)

        assert user.failed_login_attempts == 0
        assert user.last_login_at == FIXED_NOW


class TestPasswordLifecycle:
    def test_reset_sets_a_temporary_password_and_unlocks(self) -> None:
        user = make_user()
        for _ in range(5):
            user.record_failed_login(FIXED_NOW, max_attempts=5, lockout=LOCKOUT)

        user.reset_password("novo-hash")

        assert user.password_hash == "novo-hash"
        assert user.must_change_password
        assert not user.is_locked(FIXED_NOW)

    def test_change_password_clears_the_pending_change(self) -> None:
        user = make_user(must_change_password=True)

        user.change_password("definitivo")

        assert not user.must_change_password


def test_activation_and_identity() -> None:
    user = make_user()
    user.deactivate()
    assert not user.is_active
    user.activate()
    assert user.is_active
    assert user == user
    assert user != make_user()
    assert hash(user) == hash(user.id)
