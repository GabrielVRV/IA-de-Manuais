"""Origem dos manuais sincronizados com a pasta da Engenharia (ADR 0009).

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Manuais já cadastrados vieram pela tela: ficam sem origem (colunas nulas).
    op.add_column("manuals", sa.Column("source_key", sa.String(50), nullable=True))
    op.add_column("manuals", sa.Column("source_fingerprint", sa.String(100), nullable=True))
    op.add_column("manuals", sa.Column("source_content_hash", sa.String(64), nullable=True))
    op.create_unique_constraint(op.f("uq_manuals_source_key"), "manuals", ["source_key"])
    op.create_check_constraint(
        op.f("ck_manuals_source_complete"),
        "manuals",
        "(source_key IS NULL) = (source_fingerprint IS NULL)"
        " AND (source_key IS NULL) = (source_content_hash IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_manuals_source_complete"), "manuals", type_="check")
    op.drop_constraint(op.f("uq_manuals_source_key"), "manuals", type_="unique")
    op.drop_column("manuals", "source_content_hash")
    op.drop_column("manuals", "source_fingerprint")
    op.drop_column("manuals", "source_key")
