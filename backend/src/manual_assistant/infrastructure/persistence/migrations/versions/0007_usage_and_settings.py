"""Consumo de tokens por pergunta, preço por modelo e configurações alteradas pela tela.

O consumo guarda só números (usuário, data, modelo, tokens): o texto das perguntas
continua apenas no histórico de conversas.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "question_usage",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("asked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "input_tokens >= 0 AND output_tokens >= 0",
            name=op.f("ck_question_usage_valid_tokens"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_question_usage_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_question_usage")),
    )
    op.create_index("ix_question_usage_asked_at", "question_usage", ["asked_at"])
    op.create_index("ix_question_usage_user_id_asked_at", "question_usage", ["user_id", "asked_at"])

    op.create_table(
        "system_settings",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("usage_retention_months", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.CheckConstraint("id = 1", name=op.f("ck_system_settings_single_row")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_system_settings")),
    )

    op.create_table(
        "model_prices",
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("input_per_million", sa.Numeric(12, 6), nullable=False),
        sa.Column("output_per_million", sa.Numeric(12, 6), nullable=False),
        sa.PrimaryKeyConstraint("model", name=op.f("pk_model_prices")),
    )


def downgrade() -> None:
    op.drop_table("model_prices")
    op.drop_table("system_settings")
    op.drop_index("ix_question_usage_user_id_asked_at", table_name="question_usage")
    op.drop_index("ix_question_usage_asked_at", table_name="question_usage")
    op.drop_table("question_usage")
