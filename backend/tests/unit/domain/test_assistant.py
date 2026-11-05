import pytest

from manual_assistant.domain.assistant import (
    ASSISTANTS,
    DEFAULT_REQUEST_INSTRUCTIONS,
    REQUEST_INSTRUCTIONS_MAX_LENGTH,
    AccessPolicy,
    AssistantId,
    DefaultAccess,
    UserAccess,
    get_assistant,
)
from manual_assistant.domain.errors import InvalidValueError
from manual_assistant.domain.user import UserRole
from tests.security import make_user

maria = make_user("maria")
admin = make_user("admin", role=UserRole.ADMIN)


def test_every_assistant_id_has_an_assistant() -> None:
    assert {assistant.id for assistant in ASSISTANTS} == set(AssistantId)
    assert get_assistant(AssistantId.ENGINEERING).name == "Assistente de Engenharia"


class TestAccessPolicy:
    def test_is_open_to_everyone_by_default(self) -> None:
        policy = AccessPolicy(assistant_id=AssistantId.ENGINEERING)

        assert policy.default_access is DefaultAccess.OPEN
        assert policy.allows(maria, None)

    @pytest.mark.parametrize(
        ("default", "exception", "allowed"),
        [
            (DefaultAccess.OPEN, None, True),
            (DefaultAccess.OPEN, UserAccess.DENIED, False),
            (DefaultAccess.RESTRICTED, None, False),
            (DefaultAccess.RESTRICTED, UserAccess.GRANTED, True),
        ],
    )
    def test_the_user_exception_wins_over_the_default(
        self, default: DefaultAccess, exception: UserAccess | None, allowed: bool
    ) -> None:
        policy = AccessPolicy(assistant_id=AssistantId.ENGINEERING, default_access=default)

        assert policy.allows(maria, exception) is allowed

    def test_administrators_use_every_assistant(self) -> None:
        policy = AccessPolicy(
            assistant_id=AssistantId.ENGINEERING, default_access=DefaultAccess.RESTRICTED
        )

        assert policy.allows(admin, UserAccess.DENIED)

    def test_the_denial_says_how_to_ask_for_access(self) -> None:
        policy = AccessPolicy(
            assistant_id=AssistantId.ENGINEERING,
            request_instructions="  Abra um chamado no GLPI.  ",
        )

        assert policy.request_instructions == "Abra um chamado no GLPI."
        assert policy.denial_message() == (
            "Você não tem acesso ao Assistente de Engenharia. Abra um chamado no GLPI."
        )

    def test_blank_instructions_fall_back_to_the_default_message(self) -> None:
        policy = AccessPolicy(assistant_id=AssistantId.ENGINEERING, request_instructions="  ")

        assert policy.request_instructions is None
        assert policy.instructions == DEFAULT_REQUEST_INSTRUCTIONS

    def test_rejects_too_long_instructions(self) -> None:
        with pytest.raises(InvalidValueError, match="no máximo"):
            AccessPolicy(
                assistant_id=AssistantId.ENGINEERING,
                request_instructions="x" * (REQUEST_INSTRUCTIONS_MAX_LENGTH + 1),
            )
