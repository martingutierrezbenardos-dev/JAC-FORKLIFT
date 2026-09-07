from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Machine(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Ficha mínima de máquina (montacargas).

    Fase 1 solo la usa como referencia opcional en ``expenses``. Horómetro, mantenimiento
    preventivo y alertas se implementan en Fase 3.
    """

    __tablename__ = "machines"

    numero_interno: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    numero_serie: Mapped[str | None] = mapped_column(String(80), nullable=True)
    marca: Mapped[str | None] = mapped_column(String(80), nullable=True)
    modelo: Mapped[str | None] = mapped_column(String(80), nullable=True)
    tipo: Mapped[str | None] = mapped_column(String(80), nullable=True)
    cliente_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True
    )
    horometro: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estado: Mapped[str] = mapped_column(String(40), nullable=False, default="operativa")
    ubicacion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    observaciones: Mapped[str | None] = mapped_column(String, nullable=True)
