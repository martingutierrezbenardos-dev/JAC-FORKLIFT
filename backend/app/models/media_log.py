from __future__ import annotations

import uuid
from enum import Enum as PyEnum

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MediaType(str, PyEnum):
    AUDIO = "audio"
    IMAGE = "image"
    DOCUMENT = "document"


class MediaLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Registro de auditoría de cada archivo multimedia recibido por WhatsApp.

    Conserva la transcripción o los datos extraídos (sección 8 y 5 del brief: "la
    transcripción debe conservarse opcionalmente para auditoría"). ``wa_media_id`` es la
    referencia de Meta — los archivos en sí NO se almacenan de forma permanente porque no hay
    todavía un proveedor de almacenamiento de archivos configurado (ver
    docs/architecture.md, integración de almacenamiento pendiente para Fase 3+).
    """

    __tablename__ = "media_logs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    wa_media_id: Mapped[str] = mapped_column(String(120), nullable=False)
    media_type: Mapped[MediaType] = mapped_column(Enum(MediaType, name="media_type"), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
