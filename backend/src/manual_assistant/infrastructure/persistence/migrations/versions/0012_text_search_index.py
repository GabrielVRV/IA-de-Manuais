"""Índice de busca por palavras nos trechos.

A busca por sentido (embedding) sozinha deixava de fora trechos que trazem as palavras
da pergunta com outro contexto ("maternidade" x "aleitamento"). A busca por palavras usa
o full text do PostgreSQL em português (raiz das palavras: "leitão" acha "leitões").

A expressão do índice é a mesma de ``PgVectorStore.search_text``.

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "ix_chunks_text_search"


def upgrade() -> None:
    op.execute(
        f"CREATE INDEX {INDEX_NAME} ON chunks "
        "USING gin (to_tsvector('portuguese'::regconfig, text))"
    )


def downgrade() -> None:
    op.execute(f"DROP INDEX {INDEX_NAME}")
