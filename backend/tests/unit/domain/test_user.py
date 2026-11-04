from datetime import datetime

import pytest

from manual_assistant.domain.errors import InvalidValueError
from manual_assistant.domain.user import (
    AuthSource,
    User,
    UserRole,
    normalize_username,
    validate_password,
)
from tests.factories import FIXED_NOW
from tests.security import make_ad_user, make_user


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


class TestDirectoryProvisioning:
    def test_enters_awaiting_approval_without_a_password(self) -> None:
        user = User.provision_from_directory(
            username=" JOAO.Silva ", display_name="  João da Silva ", now=FIXED_NOW
        )

        assert (user.username, user.display_name) == ("joao.silva", "João da Silva")
        assert user.is_pending
        assert not user.is_local
        assert user.password_hash is None
        assert not user.must_change_password

    def test_falls_back_to_the_login_when_the_ad_has_no_name(self) -> None:
        user = User.provision_from_directory(username="joao", display_name="  ", now=FIXED_NOW)

        assert user.display_name == "joao"

    def test_long_ad_names_are_cut_to_fit(self) -> None:
        user = make_ad_user()

        user.sync_display_name("x" * 150)

        assert len(user.display_name) == 100

    @pytest.mark.parametrize(
        ("source", "password_hash"), [(AuthSource.LOCAL, None), (AuthSource.AD, "hash")]
    )
    def test_only_local_users_store_a_password(
        self, source: AuthSource, password_hash: str | None
    ) -> None:
        with pytest.raises(InvalidValueError, match="Só usuários locais"):
            User(
                id=make_user().id,
                username="maria",
                display_name="Maria",
                role=UserRole.USER,
                password_hash=password_hash,
                created_at=FIXED_NOW,
                auth_source=source,
            )

    def test_a_local_user_can_switch_to_the_ad_keeping_the_role(self) -> None:
        user = make_user(role=UserRole.ADMIN, must_change_password=True)

        user.use_directory_login()

        assert (user.auth_source, user.password_hash) == (AuthSource.AD, None)
        assert user.is_admin
        assert not user.must_change_password

    def test_switching_to_the_ad_can_take_the_network_login(self) -> None:
        user = make_ad_user("gviaro")

        user.use_directory_login(" Gabriel.Viaro ")

        assert user.username == "gabriel.viaro"

    def test_the_network_login_must_be_valid(self) -> None:
        with pytest.raises(InvalidValueError, match="login"):
            make_ad_user("gviaro").use_directory_login("gabriel viaro")


class TestPasswordLifecycle:
    def test_reset_sets_a_temporary_password(self) -> None:
        user = make_user()

        user.reset_password("novo-hash")

        assert user.password_hash == "novo-hash"
        assert user.must_change_password

    @pytest.mark.parametrize("change", ["reset_password", "change_password"])
    def test_ad_passwords_are_not_managed_here(self, change: str) -> None:
        with pytest.raises(InvalidValueError, match="troque-a no Windows"):
            getattr(make_ad_user(), change)("hash")

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
