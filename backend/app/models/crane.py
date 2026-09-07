from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import Date, Enum, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.expense import Currency


class CraneContractStatus(str, PyEnum):
    ACTIVO = "activo"
    FINALIZADO = "finalizado"
    CANCELADO = "cancelado"


class CraneContract(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Contrato de horas de grúa con un cliente (sección 16 del brief)."""

    __tablename__ = "crane_contracts"

    cliente_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True
    )
    periodo_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    periodo_fin: Mapped[date] = mapped_column(Date, nullable=False)
    horas_contratadas: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    costo_hora: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    moneda: Mapped[Currency] = mapped_column(Enum(Currency, name="currency"), default=Currency.CLP, nullable=False)
    estado: Mapped[CraneContractStatus] = mapped_column(
        Enum(CraneContractStatus, name="crane_contract_status"),
        default=CraneContractStatus.ACTIVO,
        nullable=False,
    )
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)


class CraneUsage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Registro de horas de grúa consumidas contra un contrato."""

    __tablename__ = "crane_usage"

    contrato_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("crane_contracts.id"), nullable=False, index=True
    )
    registrado_por: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    servicio_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("service_orders.id"), nullable=True
    )
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    horas_usadas: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)
