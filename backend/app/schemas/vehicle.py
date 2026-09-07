from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BuscarVehiculoInput(BaseModel):
    patente: str = Field(description="Patente del vehículo a buscar (puede ser parcial).")


class ConsultarUbicacionVehiculoInput(BaseModel):
    patente: str


class ConsultarRangoVehiculoInput(BaseModel):
    patente: str
    desde: datetime
    hasta: datetime


class VehicleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patente: str
    marca: str | None
    modelo: str | None
    anio: int | None
    sucursal: str | None
    conductor_asignado_id: uuid.UUID | None
    estado: str
    observaciones: str | None
