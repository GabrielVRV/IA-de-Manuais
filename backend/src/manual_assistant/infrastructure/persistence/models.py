"""Modelos ORM: o formato das tabelas. Ficam separados das entidades de domínio
de propósito, para que o domínio não dependa do SQLAlchemy."""

from datetime import datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    MetaData,
    Numeric,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
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
    # Origem na pasta da Engenharia (ADR 0009); nulas nos manuais enviados pela tela.
    source_key: Mapped[str | None] = mapped_column(String(50), unique=True)
    source_fingerprint: Mapped[str | None] = mapped_column(String(100))
    source_content_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'indexed', 'failed')", name="valid_status"
        ),
        # Os três campos de origem andam juntos: ou todos preenchidos, ou nenhum.
        CheckConstraint(
            "(source_key IS NULL) = (source_fingerprint IS NULL)"
            " AND (source_key IS NULL) = (source_content_hash IS NULL)",
            name="source_complete",
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
        CheckConstraint("role IN ('admin', 'user')", name="valid_role"),
        CheckConstraint("auth_source IN ('local', 'ad')", name="valid_auth_source"),
        # Só usuários locais têm senha guardada aqui; a dos usuários do AD fica no AD.
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


class ConversationRecord(Base):
    __tablename__ = "conversations"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        # A lista do histórico: conversas de um usuário, das mais recentes para as antigas.
        Index("ix_conversations_owner_id_updated_at", "owner_id", "updated_at"),
        # A limpeza por retenção busca pelas paradas há mais tempo.
        Index("ix_conversations_updated_at", "updated_at"),
    )


class ExchangeRecord(Base):
    __tablename__ = "conversation_exchanges"

    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(primary_key=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    # [{"manual_id", "manual_title", "pages"}]: a fonte como era no momento da resposta.
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    asked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (CheckConstraint("position >= 0", name="valid_position"),)


class QuestionUsageRecord(Base):
    """Consumo de cada pergunta respondida. Só números: o texto fica no histórico."""

    __tablename__ = "question_usage"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    asked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    model: Mapped[str | None] = mapped_column(String(100))
    input_tokens: Mapped[int]
    output_tokens: Mapped[int]

    __table_args__ = (
        CheckConstraint("input_tokens >= 0 AND output_tokens >= 0", name="valid_tokens"),
        # O relatório e a limpeza por retenção filtram por data.
        Index("ix_question_usage_asked_at", "asked_at"),
        Index("ix_question_usage_user_id_asked_at", "user_id", "asked_at"),
    )


class SystemSettingsRecord(Base):
    """Uma linha só (id = 1) com as configurações alteradas pela tela."""

    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)
    usage_retention_months: Mapped[int]
    questions_per_minute: Mapped[int]
    questions_per_day: Mapped[int]
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_by: Mapped[str | None] = mapped_column(String(100))

    __table_args__ = (CheckConstraint("id = 1", name="single_row"),)


class ModelPriceRecord(Base):
    __tablename__ = "model_prices"

    model: Mapped[str] = mapped_column(String(100), primary_key=True)
    # Dólares por milhão de tokens.
    input_per_million: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    output_per_million: Mapped[Decimal] = mapped_column(Numeric(12, 6))


class SyncScheduleRecord(Base):
    """Uma linha só (id = 1): o agendamento da sincronização com a pasta da Engenharia."""

    __tablename__ = "sync_schedule"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)
    enabled: Mapped[bool] = mapped_column(Boolean)
    time_of_day: Mapped[time] = mapped_column(Time())  # no relógio da empresa (APP_TIMEZONE)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_by: Mapped[str | None] = mapped_column(String(100))
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_trigger_error: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (CheckConstraint("id = 1", name="single_row"),)


class AssistantAccessPolicyRecord(Base):
    """Acesso padrão de cada assistente do chat. Sem linha = liberado para todos."""

    __tablename__ = "assistant_access_policies"

    assistant_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    default_access: Mapped[str] = mapped_column(String(20))
    request_instructions: Mapped[str | None] = mapped_column(String(300))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_by: Mapped[str | None] = mapped_column(String(100))

    __table_args__ = (
        CheckConstraint("default_access IN ('open', 'restricted')", name="valid_default_access"),
    )


class UserAssistantAccessRecord(Base):
    """Exceção ao acesso padrão de um assistente, para um usuário."""

    __tablename__ = "user_assistant_access"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    assistant_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    access: Mapped[str] = mapped_column(String(20))

    __table_args__ = (CheckConstraint("access IN ('granted', 'denied')", name="valid_access"),)
