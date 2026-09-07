from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.expense import Currency, ExpenseCategory, PaymentMethod, ReimbursementStatus


class ExpenseCreate(BaseModel):
    """Input tanto para la API REST como para la tool ``crear_gasto`` del agente de IA.

    Deliberadamente NO incluye ``user_id``: el gasto siempre se registra para el usuario
    autenticado (o el usuario de WhatsApp que escribe), nunca para otro por spoofing de un
    parámetro.
    """

    fecha: date
    monto: Decimal = Field(gt=0)
    moneda: Currency = Currency.CLP
    categoria: ExpenseCategory
    proveedor: str | None = None
    descripcion: str | None = None
    cliente_nombre: str | None = Field(
        default=None, description="Nombre del cliente, si el gasto está asociado a uno."
    )
    maquina_numero: str | None = Field(
        default=None, description="Número interno de la máquina, si corresponde."
    )
    forma_pago: PaymentMethod
    pagado_por_telefono: str | None = Field(
        default=None, description="Teléfono WhatsApp de quién pagó, si es distinto de quien registra."
    )
    requiere_reembolso: bool | None = Field(
        default=None,
        description="Si no se especifica, se infiere: True cuando forma_pago=efectivo_propio.",
    )
    comprobante_url: str | None = None
    observaciones: str | None = None


class ExpenseUpdate(BaseModel):
    monto: Decimal | None = Field(default=None, gt=0)
    categoria: ExpenseCategory | None = None
    proveedor: str | None = None
    descripcion: str | None = None
    estado_reembolso: ReimbursementStatus | None = None
    observaciones: str | None = None
    comprobante_url: str | None = None


class ExpenseUpdateToolInput(ExpenseUpdate):
    gasto_id: str | None = Field(
        default=None,
        description=(
            "ID del gasto a modificar. Si no se indica, se usa el último gasto registrado "
            "por quien escribe."
        ),
    )


class ExpenseSearchParams(BaseModel):
    desde: date | None = None
    hasta: date | None = None
    categoria: ExpenseCategory | None = None
    proveedor: str | None = None
    estado_reembolso: ReimbursementStatus | None = None
    usuario_telefono: str | None = Field(
        default=None,
        description="Solo tiene efecto si quien pregunta tiene permiso de ver gastos de todos.",
    )


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    fecha: date
    monto: Decimal
    moneda: Currency
    categoria: ExpenseCategory
    proveedor: str | None
    descripcion: str | None
    cliente_id: uuid.UUID | None
    maquina_id: uuid.UUID | None
    forma_pago: PaymentMethod
    pagado_por: uuid.UUID | None
    requiere_reembolso: bool
    estado_reembolso: ReimbursementStatus | None
    comprobante_url: str | None
    observaciones: str | None
    created_at: datetime
    updated_at: datetime
