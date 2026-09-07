from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import Enum as PyEnum

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ServiceOrderStatus(str, PyEnum):
    PENDIENTE = "pendiente"
    ASIGNADO = "asignado"
    EN_RUTA = "en_ruta"
    EN_SERVICIO = "en_servicio"
    TERMINADO = "terminado"
    CERRADO = "cerrado"
    CANCELADO = "cancelado"


class ServiceOrder(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """Orden de servicio técnico (visita a un cliente para revisar/reparar una máquina).

    ``numero`` se genera desde la secuencia ``service_order_number_seq`` (ver migración
    0002) para evitar colisiones si dos técnicos registran servicios al mismo tiempo.
    """

    __tablename__ = "service_orders"

    numero: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    cliente_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True
    )
    maquina_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("machines.id"), nullable=True
    )
    tecnico_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    hora_salida: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hora_llegada: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hora_inicio: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hora_termino: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)
    diagnostico: Mapped[str | None] = mapped_column(Text, nullable=True)
    trabajo_realizado: Mapped[str | None] = mapped_column(Text, nullable=True)
    repuestos_utilizados: Mapped[str | None] = mapped_column(Text, nullable=True)
    resultado: Mapped[str | None] = mapped_column(Text, nullable=True)
    estado: Mapped[ServiceOrderStatus] = mapped_column(
        Enum(ServiceOrderStatus, name="service_order_status"),
        default=ServiceOrderStatus.PENDIENTE,
        nullable=False,
    )
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)
