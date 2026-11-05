"""Agendamento diário da sincronização com a pasta da Engenharia, configurado pela tela.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sync_schedule",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("time_of_day", sa.Time(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_trigger_error", sa.String(500), nullable=True),
        sa.CheckConstraint("id = 1", name=op.f("ck_sync_schedule_single_row")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sync_schedule")),
    )


def downgrade() -> None:
    op.drop_table("sync_schedule")
