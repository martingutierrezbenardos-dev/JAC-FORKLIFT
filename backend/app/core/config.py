"""Configuración centralizada de la aplicación.

Toda variable de entorno se lee EXCLUSIVAMENTE aquí. Ningún otro módulo debe llamar a
``os.environ`` directamente — así hay un solo lugar que documenta qué variables existen
(ver ``.env.example``) y un solo lugar que valida su formato al arrancar.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Entorno
    environment: str = Field(default="development")
    debug: bool = Field(default=True)

    # Base de datos
    database_url: str = Field(
        default="postgresql+psycopg://jacobea:jacobea@localhost:5432/jacobea_dev"
    )

    # Autenticación panel web
    jwt_secret_key: str = Field(default="CHANGE_ME_INSECURE_DEV_ONLY")
    jwt_algorithm: str = Field(default="HS256")
    jwt_access_token_expire_minutes: int = Field(default=30)

    # WhatsApp Cloud API (Meta)
    whatsapp_api_version: str = Field(default="v20.0")
    whatsapp_phone_number_id: str | None = Field(default=None)
    whatsapp_access_token: str | None = Field(default=None)
    whatsapp_app_secret: str | None = Field(default=None)
    whatsapp_verify_token: str | None = Field(default=None)

    # LLM (Anthropic)
    anthropic_api_key: str | None = Field(default=None)
    anthropic_model: str = Field(default="claude-sonnet-5")
    max_tool_iterations: int = Field(default=6)
    conversation_history_length: int = Field(default=20)

    # Rate limiting
    rate_limit_webhook: str = Field(default="30/minute")
    rate_limit_login: str = Field(default="10/minute")

    # CORS (panel web)
    cors_allowed_origins: str = Field(default="http://localhost:3000")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
