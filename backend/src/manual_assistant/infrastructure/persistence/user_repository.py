from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from manual_assistant.application.errors import UserAlreadyExistsError
from manual_assistant.domain.user import AuthSource, User, UserId, UserRole
from manual_assistant.infrastructure.persistence.database import translate_database_errors
from manual_assistant.infrastructure.persistence.models import UserRecord

_IMMUTABLE_COLUMNS = frozenset({"id", "created_at"})


class SqlAlchemyUserRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save(self, user: User) -> None:
        values = _to_row(user)
        statement = insert(UserRecord).values(**values)
        statement = statement.on_conflict_do_update(
            index_elements=[UserRecord.id],
            set_={
                **{c: statement.excluded[c] for c in values if c not in _IMMUTABLE_COLUMNS},
                "updated_at": func.now(),
            },
        )
        async with (
            translate_database_errors("salvar o usuário"),
            self._session_factory.begin() as session,
        ):
            try:
                await session.execute(statement)
            except IntegrityError as error:
                # O índice único do login é a garantia final contra cadastros simultâneos.
                raise UserAlreadyExistsError(user.username) from error

    async def get(self, user_id: UserId) -> User | None:
        async with (
            translate_database_errors("buscar o usuário"),
            self._session_factory() as session,
        ):
            record = await session.get(UserRecord, user_id)
        return _to_entity(record) if record else None

    async def get_by_username(self, username: str) -> User | None:
        statement = select(UserRecord).where(UserRecord.username == username)
        async with (
            translate_database_errors("buscar o usuário"),
            self._session_factory() as session,
        ):
            record = await session.scalar(statement)
        return _to_entity(record) if record else None

    async def list_all(self) -> Sequence[User]:
        statement = select(UserRecord).order_by(UserRecord.display_name)
        async with (
            translate_database_errors("listar os usuários"),
            self._session_factory() as session,
        ):
            records = (await session.scalars(statement)).all()
        return [_to_entity(record) for record in records]


def _to_row(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role.value,
        "auth_source": user.auth_source.value,
        "password_hash": user.password_hash,
        "is_active": user.is_active,
        "must_change_password": user.must_change_password,
        "last_login_at": user.last_login_at,
        "created_at": user.created_at,
    }


def _to_entity(record: UserRecord) -> User:
    return User(
        id=UserId(record.id),
        username=record.username,
        display_name=record.display_name,
        role=UserRole(record.role),
        password_hash=record.password_hash,
        created_at=record.created_at,
        auth_source=AuthSource(record.auth_source),
        is_active=record.is_active,
        must_change_password=record.must_change_password,
        last_login_at=record.last_login_at,
    )
