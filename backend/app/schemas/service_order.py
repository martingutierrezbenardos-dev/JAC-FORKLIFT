from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.service_order import ServiceOrderStatus


class ServiceOrderCreate(BaseModel):
    motivo: str = Field(min_length=3, description="Motivo de la visita o el servicio.")
    cliente_nombre: str | None = None
    maquina_numero: str | None = None


class ServiceOrderUpdate(BaseModel):
    servicio_numero: str | None = Field(
        default=None,
        description=(
            "Número de la orden de servicio (ej. 'OT-000123'). Si no se indica, se usa la "
            "orden de servicio más reciente y aún abierta de quien escribe."
        ),
    )
    cliente_nombre: str | None = None
    maquina_numero: str | None = None
    hora_salida: datetime | None = None
    hora_llegada: datetime | None = None
    hora_inicio: datetime | None = None
    hora_termino: datetime | None = None
    diagnostico: str | None = None
    trabajo_realizado: str | None = None
    repuestos_utilizados: str | None = None
    resultado: str | None = None
    estado: ServiceOrderStatus | None = None
    observaciones: str | None = None


class ServiceOrderSearchParams(BaseModel):
    estado: ServiceOrderStatus | None = None
    tecnico_telefono: str | None = None
    cliente_nombre: str | None = None


class ServiceOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    numero: str
    cliente_id: uuid.UUID | None
    maquina_id: uuid.UUID | None
    tecnico_id: uuid.UUID
    fecha: date
    hora_salida: datetime | None
    hora_llegada: datetime | None
    hora_inicio: datetime | None
    hora_termino: datetime | None
    motivo: str | None
    diagnostico: str | None
    trabajo_realizado: str | None
    repuestos_utilizados: str | None
    resultado: str | None
    estado: ServiceOrderStatus
    observaciones: str | None
    created_at: datetime
    updated_at: datetime
