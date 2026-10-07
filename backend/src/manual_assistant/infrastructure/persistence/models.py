"""Modelos ORM: o formato das tabelas. Ficam separados das entidades de domínio
de propósito, para que o domínio não dependa do SQLAlchemy."""

from datetime import datetime
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Precisa ser igual ao tamanho dos vetores do provedor de embeddings.
# Alterar exige uma nova migração e a reindexação de todos os manuais.
EMBEDDING_DIMENSIONS = 1536

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class ManualRecord(Base):
    __tablename__ = "manuals"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    file_name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20))
    page_count: Mapped[int | None]
    chunk_count: Mapped[int | None]
    failure_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'indexed', 'failed')", name="valid_status"
        ),
        Index("ix_manuals_created_at", "created_at"),
    )


class ChunkRecord(Base):
    __tablename__ = "chunks"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    manual_id: Mapped[UUID] = mapped_column(ForeignKey("manuals.id", ondelete="CASCADE"))
    position: Mapped[int]
    text: Mapped[str] = mapped_column(Text)
    page_start: Mapped[int]
    page_end: Mapped[int]
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS))

    __table_args__ = (
        UniqueConstraint("manual_id", "position", name="uq_chunks_manual_id_position"),
        CheckConstraint("page_start >= 1 AND page_end >= page_start", name="valid_pages"),
        # HNSW: índice aproximado que mantém a busca rápida mesmo com milhares de trechos.
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
