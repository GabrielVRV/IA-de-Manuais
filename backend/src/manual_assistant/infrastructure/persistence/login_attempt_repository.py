from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from manual_assistant.domain.login_attempts import LoginAttempts
from manual_assistant.infrastructure.persistence.database import translate_database_errors
from manual_assistant.infrastructure.persistence.models import LoginAttemptRecord


class SqlAlchemyLoginAttemptRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get(self, username: str) -> LoginAttempts:
        async with (
            translate_database_errors("consultar as tentativas de login"),
            self._session_factory() as db,
        ):
            record = await db.get(LoginAttemptRecord, username)
        if record is None:
            return LoginAttempts(username=username)
        return LoginAttempts(
            username=record.username,
            failed_count=record.failed_count,
            locked_until=record.locked_until,
        )

    async def save(self, attempts: LoginAttempts) -> None:
        values = {"failed_count": attempts.failed_count, "locked_until": attempts.locked_until}
        statement = insert(LoginAttemptRecord).values(username=attempts.username, **values)
        statement = statement.on_conflict_do_update(
            index_elements=[LoginAttemptRecord.username], set_=values
        )
        async with (
            translate_database_errors("registrar a tentativa de login"),
            self._session_factory.begin() as db,
        ):
            await db.execute(statement)

    async def clear(self, username: str) -> None:
        statement = delete(LoginAttemptRecord).where(LoginAttemptRecord.username == username)
        async with (
            translate_database_errors("limpar as tentativas de login"),
            self._session_factory.begin() as db,
        ):
            await db.execute(statement)
