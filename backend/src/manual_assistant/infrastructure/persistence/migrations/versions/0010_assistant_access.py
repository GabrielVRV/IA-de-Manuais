"""Acesso por assistente do chat e fim do perfil "aguardando liberação" (ADR 0013).

Quem entra pelo AD passa a usar direto os assistentes liberados para todos; quem
estava aguardando liberação vira usuário comum.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assistant_access_policies",
        sa.Column("assistant_id", sa.String(30), nullable=False),
        sa.Column("default_access", sa.String(20), nullable=False),
        sa.Column("request_instructions", sa.String(300), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.CheckConstraint(
            "default_access IN ('open', 'restricted')",
            name=op.f("ck_assistant_access_policies_valid_default_access"),
        ),
        sa.PrimaryKeyConstraint("assistant_id", name=op.f("pk_assistant_access_policies")),
    )
    op.create_table(
        "user_assistant_access",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("assistant_id", sa.String(30), nullable=False),
        sa.Column("access", sa.String(20), nullable=False),
        sa.CheckConstraint(
            "access IN ('granted', 'denied')", name=op.f("ck_user_assistant_access_valid_access")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_assistant_access_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "assistant_id", name=op.f("pk_user_assistant_access")),
    )

    op.drop_constraint(op.f("ck_users_valid_role"), "users", type_="check")
    op.execute("UPDATE users SET role = 'user' WHERE role = 'pending'")
    op.create_check_constraint(op.f("ck_users_valid_role"), "users", "role IN ('admin', 'user')")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_users_valid_role"), "users", type_="check")
    op.create_check_constraint(
        op.f("ck_users_valid_role"), "users", "role IN ('admin', 'user', 'pending')"
    )
    op.drop_table("user_assistant_access")
    op.drop_table("assistant_access_policies")
