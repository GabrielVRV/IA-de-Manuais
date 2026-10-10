from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from manual_assistant.domain.answer import Answer, Citation
from manual_assistant.domain.conversation import (
    Conversation,
    ConversationId,
    ConversationSummary,
    Exchange,
)
from manual_assistant.domain.manual import ManualId
from manual_assistant.domain.user import UserId
from manual_assistant.infrastructure.persistence.database import translate_database_errors
from manual_assistant.infrastructure.persistence.models import ConversationRecord, ExchangeRecord


class SqlAlchemyConversationRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def add(self, conversation: Conversation) -> None:
        record = ConversationRecord(
            id=conversation.id,
            owner_id=conversation.owner_id,
            title=conversation.title,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )
        exchanges = [
            _exchange_record(conversation.id, position, exchange)
            for position, exchange in enumerate(conversation.exchanges)
        ]
        async with (
            translate_database_errors("salvar a conversa"),
            self._session_factory.begin() as db,
        ):
            db.add(record)
            await db.flush()  # a conversa precisa existir antes das trocas (chave estrangeira)
            db.add_all(exchanges)

    async def get(self, conversation_id: ConversationId) -> Conversation | None:
        exchanges_query = (
            select(ExchangeRecord)
            .where(ExchangeRecord.conversation_id == conversation_id)
            .order_by(ExchangeRecord.position)
        )
        async with (
            translate_database_errors("buscar a conversa"),
            self._session_factory() as db,
        ):
            record = await db.get(ConversationRecord, conversation_id)
            if record is None:
                return None
            exchanges = (await db.scalars(exchanges_query)).all()
        return Conversation(
            id=ConversationId(record.id),
            owner_id=UserId(record.owner_id),
            title=record.title,
            created_at=record.created_at,
            updated_at=record.updated_at,
            exchanges=[_exchange(e) for e in exchanges],
        )

    async def list_by_owner(self, owner_id: UserId) -> Sequence[ConversationSummary]:
        counts = (
            select(
                ExchangeRecord.conversation_id,
                func.count().label("exchange_count"),
            )
            .group_by(ExchangeRecord.conversation_id)
            .subquery()
        )
        statement = (
            select(ConversationRecord, func.coalesce(counts.c.exchange_count, 0))
            .outerjoin(counts, counts.c.conversation_id == ConversationRecord.id)
            .where(ConversationRecord.owner_id == owner_id)
            .order_by(ConversationRecord.updated_at.desc())
        )
        async with (
            translate_database_errors("listar as conversas"),
            self._session_factory() as db,
        ):
            rows = (await db.execute(statement)).all()
        return [
            ConversationSummary(
                id=ConversationId(record.id),
                title=record.title,
                created_at=record.created_at,
                updated_at=record.updated_at,
                exchange_count=count,
            )
            for record, count in rows
        ]

    async def append(self, conversation: Conversation, exchange: Exchange) -> None:
        next_position = select(func.coalesce(func.max(ExchangeRecord.position) + 1, 0)).where(
            ExchangeRecord.conversation_id == conversation.id
        )
        async with (
            translate_database_errors("salvar a mensagem"),
            self._session_factory.begin() as db,
        ):
            # Trava a conversa: duas abas respondendo ao mesmo tempo não disputam a posição.
            await db.execute(
                select(ConversationRecord.id)
                .where(ConversationRecord.id == conversation.id)
                .with_for_update()
            )
            position = (await db.execute(next_position)).scalar_one()
            db.add(_exchange_record(conversation.id, position, exchange))
            await db.execute(
                update(ConversationRecord)
                .where(ConversationRecord.id == conversation.id)
                .values(updated_at=conversation.updated_at)
            )

    async def rename(self, conversation_id: ConversationId, title: str) -> None:
        statement = (
            update(ConversationRecord)
            .where(ConversationRecord.id == conversation_id)
            .values(title=title)
        )
        async with (
            translate_database_errors("renomear a conversa"),
            self._session_factory.begin() as db,
        ):
            await db.execute(statement)

    async def delete(self, conversation_id: ConversationId) -> None:
        statement = delete(ConversationRecord).where(ConversationRecord.id == conversation_id)
        async with (
            translate_database_errors("apagar a conversa"),
            self._session_factory.begin() as db,
        ):
            await db.execute(statement)

    async def delete_idle(self, *, updated_before: datetime) -> int:
        statement = (
            delete(ConversationRecord)
            .where(ConversationRecord.updated_at < updated_before)
            .returning(ConversationRecord.id)
        )
        async with (
            translate_database_errors("apagar conversas antigas"),
            self._session_factory.begin() as db,
        ):
            return len((await db.execute(statement)).all())


def _exchange_record(
    conversation_id: ConversationId, position: int, exchange: Exchange
) -> ExchangeRecord:
    return ExchangeRecord(
        conversation_id=conversation_id,
        position=position,
        question=exchange.question,
        answer=exchange.answer.text,
        citations=[_citation_row(c) for c in exchange.answer.citations],
        asked_at=exchange.asked_at,
    )


def _citation_row(citation: Citation) -> dict[str, Any]:
    return {
        "manual_id": str(citation.manual_id),
        "manual_title": citation.manual_title,
        "pages": list(citation.pages),
    }


def _exchange(record: ExchangeRecord) -> Exchange:
    citations = tuple(
        Citation(
            manual_id=ManualId(UUID(str(row["manual_id"]))),
            manual_title=str(row["manual_title"]),
            pages=tuple(int(p) for p in row["pages"]),
        )
        for row in record.citations
    )
    return Exchange(
        question=record.question,
        answer=Answer(text=record.answer, citations=citations),
        asked_at=record.asked_at,
    )
