"""Descrição das figuras das páginas por IA (ADR 0014).

A sincronização agendada ganha a opção de também descrever as figuras.

Os trechos ganham um tipo ("text" ou "figure"): as figuras podem ser refeitas sem
apagar os trechos de texto. As descrições ficam numa tabela própria, para não pagar
de novo a cada reindexação.

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("manuals", sa.Column("figure_count", sa.Integer(), nullable=True))
    # Manuais já indexados: nenhuma figura descrita ainda.
    op.execute("UPDATE manuals SET figure_count = 0 WHERE status = 'indexed'")

    op.add_column(
        "chunks",
        sa.Column("kind", sa.String(10), server_default="text", nullable=False),
    )
    op.create_check_constraint(op.f("ck_chunks_valid_kind"), "chunks", "kind IN ('text', 'figure')")
    op.drop_constraint("uq_chunks_manual_id_position", "chunks", type_="unique")
    op.create_unique_constraint(
        "uq_chunks_manual_id_kind_position", "chunks", ["manual_id", "kind", "position"]
    )

    op.add_column(
        "sync_schedule",
        sa.Column("describe_figures", sa.Boolean(), server_default=sa.false(), nullable=False),
    )

    op.create_table(
        "figure_descriptions",
        sa.Column("manual_id", sa.Uuid(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("described_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("page >= 1", name=op.f("ck_figure_descriptions_valid_page")),
        sa.CheckConstraint(
            "input_tokens >= 0 AND output_tokens >= 0",
            name=op.f("ck_figure_descriptions_valid_tokens"),
        ),
        sa.ForeignKeyConstraint(
            ["manual_id"],
            ["manuals.id"],
            name=op.f("fk_figure_descriptions_manual_id_manuals"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("manual_id", "page", name=op.f("pk_figure_descriptions")),
    )


def downgrade() -> None:
    op.drop_table("figure_descriptions")
    op.drop_column("sync_schedule", "describe_figures")
    op.execute("DELETE FROM chunks WHERE kind = 'figure'")
    op.drop_constraint("uq_chunks_manual_id_kind_position", "chunks", type_="unique")
    op.create_unique_constraint("uq_chunks_manual_id_position", "chunks", ["manual_id", "position"])
    op.drop_constraint(op.f("ck_chunks_valid_kind"), "chunks", type_="check")
    op.drop_column("chunks", "kind")
    op.drop_column("manuals", "figure_count")
