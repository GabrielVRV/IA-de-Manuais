"""Login pelo Active Directory no lugar do TOTVS (ADR 0011).

Quem entrava pelo TOTVS passa a entrar pelo AD com o mesmo login, mantendo perfil e
histórico. Se o login de rede for outro, ajuste com o comando ``use-ad --ad-login``.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CHECK = "ck_users_valid_auth_source"


def upgrade() -> None:
    op.drop_constraint(op.f(_CHECK), "users", type_="check")
    op.execute("UPDATE users SET auth_source = 'ad' WHERE auth_source = 'totvs'")
    op.create_check_constraint(op.f(_CHECK), "users", "auth_source IN ('local', 'ad')")


def downgrade() -> None:
    op.drop_constraint(op.f(_CHECK), "users", type_="check")
    op.execute("UPDATE users SET auth_source = 'totvs' WHERE auth_source = 'ad'")
    op.create_check_constraint(op.f(_CHECK), "users", "auth_source IN ('local', 'totvs')")
