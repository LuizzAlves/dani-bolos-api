"""
Configuração centralizada via variáveis de ambiente.
Usa pydantic-settings para validar e carregar do .env.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """Configurações do Motor de Atendimento."""

    # --- PostgreSQL ---
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:senha@localhost:5432/confeitaria_motor",
        description="URL de conexão async com o banco de dados",
    )

    # --- Evolution API ---
    EVOLUTION_API_URL: str = Field(default="", description="URL base da Evolution API")
    EVOLUTION_API_TOKEN: str = Field(default="", description="Token de autenticação")
    EVOLUTION_INSTANCE_NAME: str = Field(default="confeitaria", description="Nome da instância WhatsApp")
    WEBHOOK_TOKEN: str = Field(default="", description="Token de segurança esperado no header X-Webhook-Token")

    # --- Google Sheets ---
    GOOGLE_SHEETS_ENABLED: bool = Field(default=False, description="Habilitar integração com Sheets")
    GOOGLE_SHEETS_WEBAPP_URL: str = Field(default="", description="URL do Web App do Apps Script")
    GOOGLE_SHEETS_WEBAPP_TOKEN: str = Field(default="", description="Token de autenticação para o Apps Script")
    GOOGLE_SHEETS_TIMEOUT_SECONDS: int = Field(default=10, description="Timeout para as requisições HTTP")

    # --- IA tradutora ---
    AI_TRANSLATOR_ENABLED: bool = Field(default=False, description="Ativa o tradutor semântico Groq")
    GROQ_API_KEY: str = Field(default="", description="Chave da API Groq")
    GROQ_TRANSLATOR_MODEL: str = Field(default="llama-3.1-8b-instant", description="Modelo Groq")

    # --- Motor ---
    MAX_FALLBACK_COUNT: int = Field(default=3, description="Máximo de fallbacks antes do humano")
    HUMAN_LOCK_HOURS: int = Field(default=4, description="Horas de human_lock")
    DEFAULT_TIMEOUT_MINUTES: int = Field(default=120, description="Timeout de conversa inativa")

    # --- Admin ---
    ADMIN_TOKEN: str = Field(default="trocar_por_token_seguro", description="Token para endpoints admin")

    # --- App ---
    APP_ENV: str = Field(default="development", description="Ambiente: development, production")
    LOG_LEVEL: str = Field(default="DEBUG", description="Nível de log")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache
def get_settings() -> Settings:
    """Retorna instância cacheada das configurações."""
    return Settings()
