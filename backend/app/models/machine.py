from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Machine(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Ficha de máquina (montacargas), incluido el estado de mantenimiento (Fase 3)."""

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

    # Mantenimiento preventivo (Fase 3) — actualizados por
    # app/services/maintenance_service.py::create_maintenance_record cada vez que se
    # registra un mantenimiento; nunca se editan a mano desde otro lugar.
    fecha_ultimo_mantenimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha_proximo_mantenimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
    horas_proximo_mantenimiento: Mapped[int | None] = mapped_column(Integer, nullable=True)
    intervalo_dias_mantenimiento: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Cada cuántos días corresponde el próximo mantenimiento, si aplica."
    )
    intervalo_horas_mantenimiento: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Cada cuántas horas de horómetro corresponde el próximo mantenimiento, si aplica."
    )
