from datetime import datetime

from sqlalchemy import delete, or_, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from manual_assistant.domain.session import Session
from manual_assistant.domain.user import UserId
from manual_assistant.infrastructure.persistence.database import translate_database_errors
from manual_assistant.infrastructure.persistence.models import SessionRecord


class SqlAlchemySessionRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def add(self, session: Session) -> None:
        record = SessionRecord(
            token_hash=session.token_hash,
            user_id=session.user_id,
            created_at=session.created_at,
            last_seen_at=session.last_seen_at,
        )
        async with (
            translate_database_errors("abrir a sessão"),
            self._session_factory.begin() as db,
        ):
            db.add(record)

    async def get(self, token_hash: str) -> Session | None:
        async with (
            translate_database_errors("buscar a sessão"),
            self._session_factory() as db,
        ):
            record = await db.get(SessionRecord, token_hash)
        if record is None:
            return None
        return Session(
            token_hash=record.token_hash,
            user_id=UserId(record.user_id),
            created_at=record.created_at,
            last_seen_at=record.last_seen_at,
        )

    async def touch(self, token_hash: str, last_seen_at: datetime) -> None:
        statement = (
            update(SessionRecord)
            .where(SessionRecord.token_hash == token_hash)
            .values(last_seen_at=last_seen_at)
        )
        async with (
            translate_database_errors("atualizar a sessão"),
            self._session_factory.begin() as db,
        ):
            await db.execute(statement)

    async def delete(self, token_hash: str) -> None:
        statement = delete(SessionRecord).where(SessionRecord.token_hash == token_hash)
        async with (
            translate_database_errors("encerrar a sessão"),
            self._session_factory.begin() as db,
        ):
            await db.execute(statement)

    async def delete_expired(self, *, last_seen_before: datetime, created_before: datetime) -> None:
        statement = delete(SessionRecord).where(
            or_(
                SessionRecord.last_seen_at < last_seen_before,
                SessionRecord.created_at < created_before,
            )
        )
        async with (
            translate_database_errors("apagar sessões expiradas"),
            self._session_factory.begin() as db,
        ):
            await db.execute(statement)
