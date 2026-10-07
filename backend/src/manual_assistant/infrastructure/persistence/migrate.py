"""Aplica as migrações pendentes do banco.

Uso: ``python -m manual_assistant.infrastructure.persistence.migrate``
(executado automaticamente ao iniciar o container da API).
"""

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import URL

from manual_assistant.infrastructure.settings import Settings

MIGRATIONS_PATH = Path(__file__).parent / "migrations"


def build_alembic_config(database_url: URL) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_PATH))
    config.attributes["database_url"] = database_url
    return config


def upgrade_to_head(database_url: URL) -> None:
    command.upgrade(build_alembic_config(database_url), "head")


def downgrade_to_base(database_url: URL) -> None:
    command.downgrade(build_alembic_config(database_url), "base")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    upgrade_to_head(Settings().database_url)


if __name__ == "__main__":
    main()
