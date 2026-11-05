from datetime import datetime
from typing import Self

from pydantic import BaseModel, Field

from manual_assistant.application.use_cases.assistant_access import (
    AssistantPolicy,
    AvailableAssistant,
)
from manual_assistant.domain.assistant import (
    REQUEST_INSTRUCTIONS_MAX_LENGTH,
    AssistantId,
    DefaultAccess,
    UserAccess,
)


class AvailableAssistantResponse(BaseModel):
    id: AssistantId
    name: str
    topic: str
    allowed: bool = Field(description="Se quem está usando pode conversar com este assistente")
    request_instructions: str = Field(description="Como pedir acesso, para quem não tem")

    @classmethod
    def from_entity(cls, available: AvailableAssistant) -> Self:
        return cls(
            id=available.assistant.id,
            name=available.assistant.name,
            topic=available.assistant.topic,
            allowed=available.allowed,
            request_instructions=available.request_instructions,
        )


class AccessPolicyResponse(BaseModel):
    assistant_id: AssistantId
    name: str
    default_access: DefaultAccess = Field(
        description="open = liberado para todos; restricted = só para quem for liberado"
    )
    request_instructions: str | None = Field(description="None = mensagem padrão")
    updated_at: datetime | None
    updated_by: str | None

    @classmethod
    def from_entity(cls, item: AssistantPolicy) -> Self:
        return cls(
            assistant_id=item.assistant.id,
            name=item.assistant.name,
            default_access=item.policy.default_access,
            request_instructions=item.policy.request_instructions,
            updated_at=item.policy.updated_at,
            updated_by=item.policy.updated_by,
        )


class UpdateAccessPolicyRequest(BaseModel):
    default_access: DefaultAccess
    request_instructions: str | None = Field(
        default=None,
        max_length=REQUEST_INSTRUCTIONS_MAX_LENGTH,
        examples=["Abra um chamado no GLPI pedindo acesso ao Assistente de Engenharia."],
    )


class SetUserAccessRequest(BaseModel):
    access: UserAccess | None = Field(description="null = seguir o acesso padrão do assistente")
