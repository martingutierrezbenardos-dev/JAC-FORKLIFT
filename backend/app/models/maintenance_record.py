from __future__ import annotations

import uuid
from datetime import date
from enum import Enum as PyEnum

from sqlalchemy import Date, Enum, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MaintenanceType(str, PyEnum):
    PREVENTIVO = "preventivo"
    CORRECTIVO = "correctivo"


class MaintenanceRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Registro de un mantenimiento realizado a una máquina (sección 11 del brief).

    Cada registro nuevo actualiza los campos de mantenimiento de ``machines`` (ver
    ``app/services/maintenance_service.py``) para que la ficha de la máquina y las alertas
    siempre reflejen el último mantenimiento sin tener que recalcular sobre el historial
    completo en cada consulta.
    """

    __tablename__ = "maintenance_records"

    maquina_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("machines.id"), nullable=False, index=True
    )
    tecnico_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    tipo: Mapped[MaintenanceType] = mapped_column(Enum(MaintenanceType, name="maintenance_type"), nullable=False)
    horometro: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trabajos_realizados: Mapped[str] = mapped_column(Text, nullable=False)
    repuestos_utilizados: Mapped[str | None] = mapped_column(Text, nullable=True)
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)
    proximo_mantenimiento_fecha: Mapped[date | None] = mapped_column(Date, nullable=True)
    proximo_mantenimiento_horas: Mapped[int | None] = mapped_column(Integer, nullable=True)
