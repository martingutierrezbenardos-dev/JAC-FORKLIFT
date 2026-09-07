from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class AuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_logs"

    usuario_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    accion: Mapped[str] = mapped_column(String(40), nullable=False)
    entidad: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entidad_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    datos_anteriores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    datos_nuevos: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    canal: Mapped[str] = mapped_column(String(20), nullable=False, default="system")
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
