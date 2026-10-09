"""Login pelo TOTVS, sessões no banco e bloqueio por login digitado (ADR 0008).

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Nomes com op.f(): sem ele, o Alembic aplica a convenção de nomes de novo sobre um nome
# já completo. Foi o que aconteceu com a regra de perfis criada na 0002.
_OLD_ROLE_CHECK = "ck_users_ck_users_valid_role"


def upgrade() -> None:
    # Usuários existentes viram locais, com a senha e o perfil que já têm.
    op.add_column(
        "users",
        sa.Column("auth_source", sa.String(20), server_default="local", nullable=False),
    )
    op.alter_column("users", "auth_source", server_default=None)
    op.alter_column("users", "password_hash", existing_type=sa.String(255), nullable=True)
    # O bloqueio por tentativas passa para login_attempts.
    op.drop_column("users", "failed_login_attempts")
    op.drop_column("users", "locked_until")

    op.drop_constraint(op.f(_OLD_ROLE_CHECK), "users", type_="check")
    op.create_check_constraint(
        op.f("ck_users_valid_role"), "users", "role IN ('admin', 'user', 'pending')"
    )
    op.create_check_constraint(
        op.f("ck_users_valid_auth_source"), "users", "auth_source IN ('local', 'totvs')"
    )
    op.create_check_constraint(
        op.f("ck_users_password_matches_source"),
        "users",
        "(auth_source = 'local') = (password_hash IS NOT NULL)",
    )

    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("token_hash", name=op.f("pk_sessions")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
    )
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"])

    op.create_table(
        "login_attempts",
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("username", name=op.f("pk_login_attempts")),
    )


def downgrade() -> None:
    op.drop_table("login_attempts")
    op.drop_index(op.f("ix_sessions_user_id"), table_name="sessions")
    op.drop_table("sessions")

    op.drop_constraint(op.f("ck_users_password_matches_source"), "users", type_="check")
    op.drop_constraint(op.f("ck_users_valid_auth_source"), "users", type_="check")
    op.drop_constraint(op.f("ck_users_valid_role"), "users", type_="check")
    # Sem o perfil "aguardando liberação" e sem usuários do TOTVS: quem estava pendente vira
    # usuário comum, e quem entrava pelo TOTVS fica com uma senha que nunca confere ("!").
    op.execute("UPDATE users SET role = 'user' WHERE role = 'pending'")
    op.execute("UPDATE users SET password_hash = '!' WHERE password_hash IS NULL")
    op.create_check_constraint(op.f(_OLD_ROLE_CHECK), "users", "role IN ('admin', 'user')")

    op.add_column("users", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "users",
        sa.Column("failed_login_attempts", sa.Integer(), server_default="0", nullable=False),
    )
    op.alter_column("users", "failed_login_attempts", server_default=None)
    op.alter_column("users", "password_hash", existing_type=sa.String(255), nullable=False)
    op.drop_column("users", "auth_source")
