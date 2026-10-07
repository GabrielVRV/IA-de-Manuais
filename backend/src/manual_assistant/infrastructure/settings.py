from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    """Configuração da aplicação, lida de variáveis de ambiente com prefixo ``APP_``."""

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Assistente de Manuais"
    environment: Literal["development", "test", "production"] = "development"
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"],
    )

    # Banco de dados
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "manuais"
    db_user: str = "manuais"
    db_password: SecretStr  # obrigatória: nunca existe senha padrão

    # Arquivos dos manuais
    storage_dir: Path = Path("data/manuals")
    max_upload_mb: int = Field(default=50, gt=0)

    # Provedor de IA
    ai_provider: Literal["gemini", "openai"] = "gemini"
    ai_timeout_seconds: float = Field(default=60, gt=0)
    ai_attempts: int = Field(default=4, ge=1)

    gemini_api_key: SecretStr | None = None
    gemini_chat_model: str = "gemini-3.5-flash"
    gemini_embedding_model: str = "gemini-embedding-001"
    gemini_thinking_budget: int = Field(default=0, ge=0)

    openai_api_key: SecretStr | None = None
    openai_chat_model: str = "gpt-4.1-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_comma_separated(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def database_url(self) -> URL:
        """URL de conexão. Ao ser convertida em texto (ex.: logs), a senha aparece como ***."""
        return URL.create(
            "postgresql+asyncpg",
            username=self.db_user,
            password=self.db_password.get_secret_value(),
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        )

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024
