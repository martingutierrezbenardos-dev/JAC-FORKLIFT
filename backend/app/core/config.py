"""Configuración centralizada de la aplicación.

Toda variable de entorno se lee EXCLUSIVAMENTE aquí. Ningún otro módulo debe llamar a
``os.environ`` directamente — así hay un solo lugar que documenta qué variables existen
(ver ``.env.example``) y un solo lugar que valida su formato al arrancar.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
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

    @field_validator("database_url")
    @classmethod
    def _normalizar_driver_postgres(cls, v: str) -> str:
        """Fuerza el driver psycopg (v3), que es el que instala requirements.txt.

        Proveedores como Railway/Render/Heroku generan DATABASE_URL con el esquema genérico
        `postgres://` o `postgresql://` (sin especificar driver). SQLAlchemy, sin un driver
        explícito, intenta usar psycopg2 por defecto — que no está instalado en este proyecto
        — y falla con "ModuleNotFoundError: No module named 'psycopg2'". Se reescribe el
        esquema aquí, en el único lugar que lee esta variable, para que funcione sin importar
        el formato exacto que entregue el proveedor de hosting.
        """
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+psycopg://", 1)
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+psycopg://", 1)
        return v

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

    # Transcripción de audio (OpenAI Whisper) — Fase 2
    openai_api_key: str | None = Field(default=None)
    openai_transcription_model: str = Field(default="whisper-1")

    # Tamaño máximo de un archivo multimedia de WhatsApp que se procesa (bytes)
    max_media_download_bytes: int = Field(default=20 * 1024 * 1024)

    # Google Calendar / Gmail (cuenta de servicio con delegación de dominio) — Fase 3/4
    # Contenido completo del JSON de credenciales de la cuenta de servicio (no una ruta).
    google_service_account_json: str | None = Field(default=None)

    # Almacenamiento permanente de archivos (S3) — Fase 4
    # Si aws_s3_bucket no está configurado, las fotos de comprobantes se procesan al vuelo y
    # no se guardan (comportamiento de Fase 2/3). Las credenciales AWS explícitas son
    # opcionales: si se omiten, boto3 usa su cadena de credenciales estándar (perfil, rol IAM).
    aws_s3_bucket: str | None = Field(default=None)
    aws_region: str | None = Field(default=None)
    aws_access_key_id: str | None = Field(default=None)
    aws_secret_access_key: str | None = Field(default=None)

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
