from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ExpenseCategory(str, PyEnum):
    REPUESTO = "repuesto"
    COMBUSTIBLE = "combustible"
    PEAJE = "peaje"
    ALIMENTACION = "alimentacion"
    ALOJAMIENTO = "alojamiento"
    TRANSPORTE = "transporte"
    HERRAMIENTAS = "herramientas"
    INSUMOS = "insumos"
    OTROS = "otros"


class Currency(str, PyEnum):
    CLP = "CLP"
    USD = "USD"


class PaymentMethod(str, PyEnum):
    TARJETA_EMPRESA = "tarjeta_empresa"
    EFECTIVO_PROPIO = "efectivo_propio"
    TRANSFERENCIA_EMPRESA = "transferencia_empresa"
    OTRO = "otro"


class ReimbursementStatus(str, PyEnum):
    PENDIENTE = "pendiente"
    ENVIADO_A_CONTABILIDAD = "enviado_a_contabilidad"
    APROBADO = "aprobado"
    PAGADO = "pagado"
    RECHAZADO = "rechazado"


class Expense(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "expenses"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    moneda: Mapped[Currency] = mapped_column(Enum(Currency, name="currency"), default=Currency.CLP, nullable=False)
    categoria: Mapped[ExpenseCategory] = mapped_column(
        Enum(ExpenseCategory, name="expense_category"), nullable=False
    )
    proveedor: Mapped[str | None] = mapped_column(String(200), nullable=True)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    cliente_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True
    )
    maquina_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("machines.id"), nullable=True
    )
    proyecto_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    forma_pago: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod, name="payment_method"), nullable=False)
    pagado_por: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    requiere_reembolso: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    estado_reembolso: Mapped[ReimbursementStatus | None] = mapped_column(
        Enum(ReimbursementStatus, name="reimbursement_status"), nullable=True
    )
    comprobante_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)
