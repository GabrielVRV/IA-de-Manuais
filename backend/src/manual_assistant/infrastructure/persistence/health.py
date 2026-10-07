import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

HEALTH_CHECK_TIMEOUT_SECONDS = 3


class DatabaseHealthIndicator:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    @property
    def name(self) -> str:
        return "database"

    async def is_healthy(self) -> bool:
        async with asyncio.timeout(HEALTH_CHECK_TIMEOUT_SECONDS):
            async with self._engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        return True
