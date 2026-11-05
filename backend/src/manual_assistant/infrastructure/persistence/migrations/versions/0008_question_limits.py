"""Limite de perguntas por usuário (por minuto e por 24 horas), alterado pela tela.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Os mesmos padrões de SystemSettings, para a linha que já existir.
_DEFAULTS = {"questions_per_minute": "10", "questions_per_day": "200"}


def upgrade() -> None:
    for column, default in _DEFAULTS.items():
        op.add_column(
            "system_settings",
            sa.Column(column, sa.Integer(), nullable=False, server_default=default),
        )
        # O padrão só preenche a linha existente; quem grava é sempre a aplicação.
        op.alter_column("system_settings", column, server_default=None)


def downgrade() -> None:
    for column in reversed(_DEFAULTS):
        op.drop_column("system_settings", column)
