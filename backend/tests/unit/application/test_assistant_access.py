from uuid import uuid4

import pytest

from manual_assistant.application.errors import (
    AssistantAccessDeniedError,
    PermissionDeniedError,
    UserNotFoundError,
)
from manual_assistant.application.use_cases.assistant_access import (
    ListAccessPoliciesUseCase,
    ListMyAssistantsUseCase,
    ListUserAccessUseCase,
    SetUserAccessUseCase,
    UpdateAccessPolicyUseCase,
    ensure_assistant_access,
)
from manual_assistant.domain.assistant import AssistantId, DefaultAccess, UserAccess
from manual_assistant.domain.user import UserId, UserRole
from tests.factories import FIXED_NOW
from tests.fakes import InMemoryAssistantAccessRepository, InMemoryUserRepository
from tests.security import make_user

pytestmark = pytest.mark.anyio

ENGINEERING = AssistantId.ENGINEERING
admin = make_user("admin", role=UserRole.ADMIN)
maria = make_user("maria")


@pytest.fixture
def access() -> InMemoryAssistantAccessRepository:
    return InMemoryAssistantAccessRepository()


async def restrict(access: InMemoryAssistantAccessRepository, instructions: str | None) -> None:
    await UpdateAccessPolicyUseCase(access).execute(
        admin,
        ENGINEERING,
        default_access=DefaultAccess.RESTRICTED,
        request_instructions=instructions,
    )


class TestEnsureAccess:
    async def test_lets_everyone_in_while_the_assistant_is_open(
        self, access: InMemoryAssistantAccessRepository
    ) -> None:
        await ensure_assistant_access(access, maria, ENGINEERING)

    async def test_refuses_with_the_instructions_when_restricted(
        self, access: InMemoryAssistantAccessRepository
    ) -> None:
        await restrict(access, "Abra um chamado no GLPI.")

        with pytest.raises(AssistantAccessDeniedError, match="Abra um chamado no GLPI"):
            await ensure_assistant_access(access, maria, ENGINEERING)

    async def test_a_granted_user_gets_in_even_when_restricted(
        self, access: InMemoryAssistantAccessRepository
    ) -> None:
        await restrict(access, None)
        await access.set_user_access(maria.id, ENGINEERING, UserAccess.GRANTED)

        await ensure_assistant_access(access, maria, ENGINEERING)


class TestListMyAssistants:
    async def test_tells_whether_the_user_can_use_each_one(
        self, access: InMemoryAssistantAccessRepository
    ) -> None:
        await restrict(access, "Abra um chamado no GLPI.")

        (engineering,) = await ListMyAssistantsUseCase(access).execute(maria)

        assert engineering.assistant.id is ENGINEERING
        assert not engineering.allowed
        assert engineering.request_instructions == "Abra um chamado no GLPI."


class TestPolicies:
    async def test_admin_changes_the_default_access(
        self, access: InMemoryAssistantAccessRepository
    ) -> None:
        policy = await UpdateAccessPolicyUseCase(access, clock=lambda: FIXED_NOW).execute(
            admin, ENGINEERING, default_access=DefaultAccess.RESTRICTED, request_instructions=None
        )

        (listed,) = await ListAccessPoliciesUseCase(access).execute(admin)
        assert listed.policy == policy
        assert (policy.updated_at, policy.updated_by) == (FIXED_NOW, admin.display_name)

    async def test_only_admins_see_or_change_the_policies(
        self, access: InMemoryAssistantAccessRepository
    ) -> None:
        with pytest.raises(PermissionDeniedError):
            await ListAccessPoliciesUseCase(access).execute(maria)
        with pytest.raises(PermissionDeniedError):
            await UpdateAccessPolicyUseCase(access).execute(
                maria, ENGINEERING, default_access=DefaultAccess.OPEN, request_instructions=None
            )


class TestUserAccess:
    async def test_admin_grants_and_returns_a_user_to_the_default(
        self, access: InMemoryAssistantAccessRepository
    ) -> None:
        users = InMemoryUserRepository()
        await users.save(maria)
        set_access = SetUserAccessUseCase(access=access, users=users)

        granted = await set_access.execute(admin, maria.id, ENGINEERING, UserAccess.GRANTED)
        assert granted == {ENGINEERING: UserAccess.GRANTED}
        assert await ListUserAccessUseCase(access).execute(admin) == {maria.id: granted}

        assert await set_access.execute(admin, maria.id, ENGINEERING, None) == {}
        assert await ListUserAccessUseCase(access).execute(admin) == {}

    async def test_unknown_user(self, access: InMemoryAssistantAccessRepository) -> None:
        set_access = SetUserAccessUseCase(access=access, users=InMemoryUserRepository())

        with pytest.raises(UserNotFoundError):
            await set_access.execute(admin, UserId(uuid4()), ENGINEERING, UserAccess.DENIED)

    async def test_only_admins_change_user_access(
        self, access: InMemoryAssistantAccessRepository
    ) -> None:
        set_access = SetUserAccessUseCase(access=access, users=InMemoryUserRepository())

        with pytest.raises(PermissionDeniedError):
            await set_access.execute(maria, maria.id, ENGINEERING, UserAccess.GRANTED)
        with pytest.raises(PermissionDeniedError):
            await ListUserAccessUseCase(access).execute(maria)
