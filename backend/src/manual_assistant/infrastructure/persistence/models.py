"""Modelos ORM: o formato das tabelas. Ficam separados das entidades de domínio
de propósito, para que o domínio não dependa do SQLAlchemy."""

from datetime import datetime
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
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


class UserRecord(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20))
    auth_source: Mapped[str] = mapped_column(String(20))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean)
    must_change_password: Mapped[bool] = mapped_column(Boolean)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("role IN ('admin', 'user', 'pending')", name="valid_role"),
        CheckConstraint("auth_source IN ('local', 'totvs')", name="valid_auth_source"),
        # Só usuários locais têm senha guardada aqui; a dos usuários do TOTVS fica no Datasul.
        CheckConstraint(
            "(auth_source = 'local') = (password_hash IS NOT NULL)", name="password_matches_source"
        ),
    )


class SessionRecord(Base):
    __tablename__ = "sessions"

    # SHA-256 do token do cookie (o token em si nunca é gravado).
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LoginAttemptRecord(Base):
    __tablename__ = "login_attempts"

    username: Mapped[str] = mapped_column(String(50), primary_key=True)
    failed_count: Mapped[int]
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
