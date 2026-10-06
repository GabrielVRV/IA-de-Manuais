from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


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

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_comma_separated(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value
