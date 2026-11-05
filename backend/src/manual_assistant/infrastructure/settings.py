from pathlib import Path
from typing import Annotated, Literal, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    """Configuração da aplicação, lida de variáveis de ambiente com prefixo ``APP_``."""

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_parse_none_str="none",  # ex.: APP_GEMINI_THINKING_BUDGET=none
    )

    app_name: str = "Assistente de Manuais"
    environment: Literal["development", "test", "production"] = "development"
    # Fuso da empresa: o "dia" do relatório de consumo e o horário dos agendamentos.
    # Sem ele, num contêiner Docker (UTC), "00:00" seria 21:00 no horário de Brasília.
    timezone: str = "America/Sao_Paulo"
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"],
    )

    # Banco de dados
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "manuais"
    db_user: str = "manuais"
    db_password: SecretStr  # obrigatória: nunca existe senha padrão

    # Autenticação
    # A sessão cai após esse tempo sem uso, ou no prazo máximo, mesmo com uso diário.
    auth_session_idle_days: float = Field(default=7, gt=0)
    auth_session_max_days: float = Field(default=30, gt=0)
    auth_max_failed_attempts: int = Field(default=5, ge=1)
    auth_lockout_minutes: int = Field(default=15, ge=1)
    # Só ligue com HTTPS: um cookie "secure" não é enviado em conexões HTTP.
    auth_cookie_secure: bool = False

    # Login pelo Active Directory (ADR 0011). Sem servidor = só usuários locais entram.
    # Ex.: ldaps://dc01.empresa.local (mais de um, separados por vírgula).
    ad_server_urls: Annotated[list[str], NoDecode] = Field(default_factory=list)
    ad_domain: str | None = None  # ex.: empresa.local; o login vira "usuario@empresa.local"
    ad_base_dn: str | None = None  # ex.: DC=empresa,DC=local
    # Só quem está neste grupo entra. Vazio = qualquer usuário do AD (ADR 0013).
    ad_required_group_dn: str | None = None
    ad_start_tls: bool = False  # só para ldap:// (porta 389)
    ad_ca_cert_file: Path | None = None  # CA interna, em PEM; vazio = as do sistema
    ad_timeout_seconds: float = Field(default=10, gt=0)

    # Arquivos dos manuais
    storage_dir: Path = Path("data/manuals")
    max_upload_mb: int = Field(default=50, gt=0)

    # Sincronização com a pasta de manuais da Engenharia (ADR 0009). Só leitura.
    # Vazio = desligada. No Docker, a pasta de rede montada com :ro.
    sync_source_dir: Path | None = None
    # Planilha (dentro da pasta) com a descrição de cada código; vazio = sem planilha.
    sync_catalog_file: str | None = "MANUAIS PRODUTO.xlsm"
    # Idiomas importados, pela letra no fim do nome (P = português, E = inglês...).
    sync_languages: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["P"])

    # Histórico de conversas (ADR 0010): apagadas após esse tempo sem uso. 0 = guardar sempre.
    conversation_retention_days: int = Field(default=90, ge=0)

    # Busca e resposta (RAG)
    rag_top_k: int = Field(default=6, ge=1, le=20)
    # 0 = sem corte: com o Gemini, trechos sem relação ainda pontuam ~0,6.
    rag_min_score: float = Field(default=0.0, ge=0.0, le=1.0)

    # Provedor de IA
    ai_provider: Literal["gemini", "openai"] = "gemini"
    ai_timeout_seconds: float = Field(default=60, gt=0)
    ai_attempts: int = Field(default=4, ge=1)

    gemini_api_key: SecretStr | None = None
    gemini_chat_model: str = "gemini-3.5-flash"
    gemini_embedding_model: str = "gemini-embedding-001"
    # Plano gratuito: lotes menores (ex.: 20) e espera pela cota (ex.: 60 s) ao receber 429.
    # 0 = falha na hora, o esperado no plano pago.
    gemini_embedding_batch_size: int = Field(default=100, ge=1, le=100)
    gemini_quota_wait_seconds: float = Field(default=0, ge=0)
    # 0 desliga o raciocínio; "none" não envia o parâmetro (obrigatório nos modelos *-lite).
    gemini_thinking_budget: int | None = Field(default=0, ge=0)

    openai_api_key: SecretStr | None = None
    openai_chat_model: str = "gpt-4.1-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_comma_separated(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("ad_server_urls", mode="before")
    @classmethod
    def _split_server_urls(cls, value: object) -> object:
        if isinstance(value, str):
            return [url.strip() for url in value.split(",") if url.strip()]
        return value

    @field_validator("sync_languages", mode="before")
    @classmethod
    def _split_languages(cls, value: object) -> object:
        if isinstance(value, str):
            return [code.strip().upper() for code in value.split(",") if code.strip()]
        return value

    @field_validator(
        "ad_domain",
        "ad_base_dn",
        "ad_required_group_dn",
        "ad_ca_cert_file",
        "sync_source_dir",
        "sync_catalog_file",
        mode="before",
    )
    @classmethod
    def _blank_as_none(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError(f"Fuso horário desconhecido em APP_TIMEZONE: {value!r}") from error
        return value

    @model_validator(mode="after")
    def _idle_fits_in_max(self) -> Self:
        if self.auth_session_idle_days > self.auth_session_max_days:
            raise ValueError(
                "APP_AUTH_SESSION_IDLE_DAYS não pode ser maior que APP_AUTH_SESSION_MAX_DAYS"
            )
        return self

    @model_validator(mode="after")
    def _ad_is_complete(self) -> Self:
        if self.ad_server_urls and not (self.ad_domain and self.ad_base_dn):
            raise ValueError("Com APP_AD_SERVER_URLS, defina também APP_AD_DOMAIN e APP_AD_BASE_DN")
        return self

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
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024
