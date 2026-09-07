from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Vehicle(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Ficha de una camioneta/vehículo de la flota (sección 15 del brief).

    No incluye ubicación ni kilometraje en vivo — eso depende del proveedor de GPS, que
    todavía no está definido (ver ``app/integrations/gps/provider.py``). Esta tabla solo
    guarda los datos propios del vehículo, independientes del proveedor.
    """

    __tablename__ = "vehicles"

    patente: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    marca: Mapped[str | None] = mapped_column(String(80), nullable=True)
    modelo: Mapped[str | None] = mapped_column(String(80), nullable=True)
    anio: Mapped[int | None] = mapped_column(nullable=True)
    sucursal: Mapped[str | None] = mapped_column(String(120), nullable=True)
    conductor_asignado_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    estado: Mapped[str] = mapped_column(String(40), nullable=False, default="operativo")
    observaciones: Mapped[str | None] = mapped_column(String, nullable=True)
