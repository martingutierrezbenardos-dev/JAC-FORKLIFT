from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.maintenance_record import MaintenanceType


class MaintenanceCreate(BaseModel):
    maquina_numero: str = Field(description="Número interno de la máquina (ej. '33').")
    tipo: MaintenanceType = MaintenanceType.PREVENTIVO
    horometro: int | None = Field(default=None, description="Horómetro actual de la máquina, si se conoce.")
    trabajos_realizados: str = Field(min_length=3)
    repuestos_utilizados: str | None = None
    observaciones: str | None = None
    proximo_mantenimiento_fecha: date | None = Field(
        default=None,
        description=(
            "Fecha del próximo mantenimiento, si se conoce. Si no se indica, se calcula "
            "automáticamente según la regla configurada en la máquina (intervalo en días)."
        ),
    )
    proximo_mantenimiento_horas: int | None = Field(
        default=None,
        description=(
            "Horómetro al que corresponde el próximo mantenimiento, si se conoce. Si no se "
            "indica, se calcula automáticamente según la regla configurada (intervalo en horas)."
        ),
    )


class MaintenanceSearchParams(BaseModel):
    maquina_numero: str | None = None


class MaintenanceAlertParams(BaseModel):
    dias_anticipacion: int = Field(default=7, ge=0, le=90)


class MaintenanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    maquina_id: uuid.UUID
    tecnico_id: uuid.UUID
    fecha: date
    tipo: MaintenanceType
    horometro: int | None
    trabajos_realizados: str
    repuestos_utilizados: str | None
    observaciones: str | None
    proximo_mantenimiento_fecha: date | None
    proximo_mantenimiento_horas: int | None
    created_at: datetime
