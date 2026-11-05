from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from manual_assistant.domain.system_settings import SystemSettings
from manual_assistant.domain.usage import ModelPrice
from manual_assistant.infrastructure.persistence.database import translate_database_errors
from manual_assistant.infrastructure.persistence.models import (
    ModelPriceRecord,
    SystemSettingsRecord,
)

_SINGLE_ROW_ID = 1


class SqlAlchemySystemSettingsRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get(self) -> SystemSettings:
        async with (
            translate_database_errors("consultar as configurações"),
            self._session_factory() as db,
        ):
            record = await db.get(SystemSettingsRecord, _SINGLE_ROW_ID)
        if record is None:
            return SystemSettings()
        return SystemSettings(
            usage_retention_months=record.usage_retention_months,
            updated_at=record.updated_at,
            updated_by=record.updated_by,
        )

    async def save(self, settings: SystemSettings) -> None:
        values: dict[str, Any] = {
            "usage_retention_months": settings.usage_retention_months,
            "updated_at": settings.updated_at,
            "updated_by": settings.updated_by,
        }
        statement = insert(SystemSettingsRecord).values(id=_SINGLE_ROW_ID, **values)
        statement = statement.on_conflict_do_update(
            index_elements=[SystemSettingsRecord.id], set_=values
        )
        async with (
            translate_database_errors("salvar as configurações"),
            self._session_factory.begin() as db,
        ):
            await db.execute(statement)


class SqlAlchemyModelPriceRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def list_all(self) -> Sequence[ModelPrice]:
        statement = select(ModelPriceRecord).order_by(ModelPriceRecord.model)
        async with (
            translate_database_errors("listar os preços dos modelos"),
            self._session_factory() as db,
        ):
            records = (await db.scalars(statement)).all()
        return [
            ModelPrice(
                model=record.model,
                input_per_million=record.input_per_million,
                output_per_million=record.output_per_million,
            )
            for record in records
        ]

    async def save(self, price: ModelPrice) -> None:
        values = {
            "input_per_million": price.input_per_million,
            "output_per_million": price.output_per_million,
        }
        statement = insert(ModelPriceRecord).values(model=price.model, **values)
        statement = statement.on_conflict_do_update(
            index_elements=[ModelPriceRecord.model], set_=values
        )
        async with (
            translate_database_errors("salvar o preço do modelo"),
            self._session_factory.begin() as db,
        ):
            await db.execute(statement)

    async def delete(self, model: str) -> None:
        statement = delete(ModelPriceRecord).where(ModelPriceRecord.model == model)
        async with (
            translate_database_errors("remover o preço do modelo"),
            self._session_factory.begin() as db,
        ):
            await db.execute(statement)
