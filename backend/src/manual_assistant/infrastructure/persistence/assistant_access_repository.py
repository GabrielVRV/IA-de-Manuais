from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from manual_assistant.domain.assistant import (
    AccessPolicy,
    AssistantId,
    DefaultAccess,
    UserAccess,
)
from manual_assistant.domain.user import UserId
from manual_assistant.infrastructure.persistence.database import translate_database_errors
from manual_assistant.infrastructure.persistence.models import (
    AssistantAccessPolicyRecord,
    UserAssistantAccessRecord,
)

# Um assistente que deixou de existir no código não derruba a leitura: é ignorado.
_KNOWN_ASSISTANTS = {assistant.value for assistant in AssistantId}


class SqlAlchemyAssistantAccessRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_policy(self, assistant_id: AssistantId) -> AccessPolicy:
        async with (
            translate_database_errors("consultar o acesso ao assistente"),
            self._session_factory() as db,
        ):
            record = await db.get(AssistantAccessPolicyRecord, assistant_id.value)
        if record is None:
            return AccessPolicy(assistant_id=assistant_id)
        return AccessPolicy(
            assistant_id=assistant_id,
            default_access=DefaultAccess(record.default_access),
            request_instructions=record.request_instructions,
            updated_at=record.updated_at,
            updated_by=record.updated_by,
        )

    async def save_policy(self, policy: AccessPolicy) -> None:
        values: dict[str, Any] = {
            "default_access": policy.default_access.value,
            "request_instructions": policy.request_instructions,
            "updated_at": policy.updated_at,
            "updated_by": policy.updated_by,
        }
        statement = insert(AssistantAccessPolicyRecord).values(
            assistant_id=policy.assistant_id.value, **values
        )
        statement = statement.on_conflict_do_update(
            index_elements=[AssistantAccessPolicyRecord.assistant_id], set_=values
        )
        async with (
            translate_database_errors("salvar o acesso ao assistente"),
            self._session_factory.begin() as db,
        ):
            await db.execute(statement)

    async def user_access(self, user_id: UserId) -> Mapping[AssistantId, UserAccess]:
        statement = select(UserAssistantAccessRecord).where(
            UserAssistantAccessRecord.user_id == user_id
        )
        async with (
            translate_database_errors("consultar os acessos do usuário"),
            self._session_factory() as db,
        ):
            records = (await db.scalars(statement)).all()
        return {
            AssistantId(record.assistant_id): UserAccess(record.access)
            for record in records
            if record.assistant_id in _KNOWN_ASSISTANTS
        }

    async def all_user_access(self) -> Mapping[UserId, Mapping[AssistantId, UserAccess]]:
        async with (
            translate_database_errors("consultar os acessos dos usuários"),
            self._session_factory() as db,
        ):
            records = (await db.scalars(select(UserAssistantAccessRecord))).all()
        result: defaultdict[UserId, dict[AssistantId, UserAccess]] = defaultdict(dict)
        for record in records:
            if record.assistant_id in _KNOWN_ASSISTANTS:
                result[UserId(record.user_id)][AssistantId(record.assistant_id)] = UserAccess(
                    record.access
                )
        return dict(result)

    async def set_user_access(
        self, user_id: UserId, assistant_id: AssistantId, access: UserAccess | None
    ) -> None:
        statement: Any
        if access is None:
            statement = delete(UserAssistantAccessRecord).where(
                UserAssistantAccessRecord.user_id == user_id,
                UserAssistantAccessRecord.assistant_id == assistant_id.value,
            )
        else:
            statement = (
                insert(UserAssistantAccessRecord)
                .values(user_id=user_id, assistant_id=assistant_id.value, access=access.value)
                .on_conflict_do_update(
                    index_elements=[
                        UserAssistantAccessRecord.user_id,
                        UserAssistantAccessRecord.assistant_id,
                    ],
                    set_={"access": access.value},
                )
            )
        async with (
            translate_database_errors("salvar o acesso do usuário"),
            self._session_factory.begin() as db,
        ):
            await db.execute(statement)
