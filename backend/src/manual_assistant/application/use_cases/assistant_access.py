"""Quem pode usar cada assistente do chat (ADR 0013).

As operações de administração recebem quem está agindo: a regra "só administradores"
vive aqui, e não apenas na API.
"""

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from manual_assistant.application.clock import Clock, utc_now
from manual_assistant.application.errors import (
    AssistantAccessDeniedError,
    PermissionDeniedError,
    UserNotFoundError,
)
from manual_assistant.application.ports.assistant_access_repository import (
    AssistantAccessRepository,
)
from manual_assistant.application.ports.user_repository import UserRepository
from manual_assistant.domain.assistant import (
    ASSISTANTS,
    AccessPolicy,
    Assistant,
    AssistantId,
    DefaultAccess,
    UserAccess,
)
from manual_assistant.domain.user import User, UserId

logger = logging.getLogger(__name__)


def _require_admin(actor: User) -> None:
    if not actor.is_admin:
        raise PermissionDeniedError("Apenas administradores podem definir os acessos")


async def ensure_assistant_access(
    access: AssistantAccessRepository, user: User, assistant_id: AssistantId
) -> None:
    """
    Raises:
        AssistantAccessDeniedError: se o usuário não pode usar o assistente.
    """
    policy = await access.get_policy(assistant_id)
    exceptions = await access.user_access(user.id)
    if not policy.allows(user, exceptions.get(assistant_id)):
        raise AssistantAccessDeniedError(policy.denial_message())


@dataclass(frozen=True, slots=True)
class AvailableAssistant:
    assistant: Assistant
    allowed: bool
    request_instructions: str  # como pedir acesso, para quem não tem


class ListMyAssistantsUseCase:
    """Os assistentes do chat e se quem está usando pode conversar com cada um."""

    def __init__(self, access: AssistantAccessRepository) -> None:
        self._access = access

    async def execute(self, actor: User) -> Sequence[AvailableAssistant]:
        exceptions = await self._access.user_access(actor.id)
        result = []
        for assistant in ASSISTANTS:
            policy = await self._access.get_policy(assistant.id)
            result.append(
                AvailableAssistant(
                    assistant=assistant,
                    allowed=policy.allows(actor, exceptions.get(assistant.id)),
                    request_instructions=policy.instructions,
                )
            )
        return result


@dataclass(frozen=True, slots=True)
class AssistantPolicy:
    assistant: Assistant
    policy: AccessPolicy


class ListAccessPoliciesUseCase:
    def __init__(self, access: AssistantAccessRepository) -> None:
        self._access = access

    async def execute(self, actor: User) -> Sequence[AssistantPolicy]:
        _require_admin(actor)
        return [
            AssistantPolicy(assistant, await self._access.get_policy(assistant.id))
            for assistant in ASSISTANTS
        ]


class UpdateAccessPolicyUseCase:
    def __init__(self, access: AssistantAccessRepository, clock: Clock = utc_now) -> None:
        self._access = access
        self._clock = clock

    async def execute(
        self,
        actor: User,
        assistant_id: AssistantId,
        *,
        default_access: DefaultAccess,
        request_instructions: str | None,
    ) -> AccessPolicy:
        _require_admin(actor)
        policy = AccessPolicy(
            assistant_id=assistant_id,
            default_access=default_access,
            request_instructions=request_instructions,
            updated_at=self._clock(),
            updated_by=actor.display_name or actor.username,
        )
        await self._access.save_policy(policy)
        logger.info(
            "Acesso padrão de %s alterado para %s por %s",
            assistant_id,
            default_access,
            actor.username,
        )
        return policy


class ListUserAccessUseCase:
    """As exceções de todos os usuários, para a tela de usuários."""

    def __init__(self, access: AssistantAccessRepository) -> None:
        self._access = access

    async def execute(self, actor: User) -> Mapping[UserId, Mapping[AssistantId, UserAccess]]:
        _require_admin(actor)
        return await self._access.all_user_access()


class SetUserAccessUseCase:
    def __init__(self, *, access: AssistantAccessRepository, users: UserRepository) -> None:
        self._access = access
        self._users = users

    async def execute(
        self,
        actor: User,
        user_id: UserId,
        assistant_id: AssistantId,
        access: UserAccess | None,
    ) -> Mapping[AssistantId, UserAccess]:
        """Grava a exceção (``None`` = seguir o padrão) e devolve as do usuário.

        Raises:
            UserNotFoundError: usuário inexistente.
        """
        _require_admin(actor)
        if await self._users.get(user_id) is None:
            raise UserNotFoundError(user_id)
        await self._access.set_user_access(user_id, assistant_id, access)
        logger.info(
            "Acesso de %s ao %s: %s, por %s",
            user_id,
            assistant_id,
            access or "padrão",
            actor.username,
        )
        return await self._access.user_access(user_id)
