from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BuscarMaquinaInput(BaseModel):
    numero_interno: str = Field(description="Número interno de la máquina a buscar (ej. '33').")


class MachineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    numero_interno: str
    numero_serie: str | None
    marca: str | None
    modelo: str | None
    tipo: str | None
    cliente_id: uuid.UUID | None
    horometro: int | None
    estado: str
    ubicacion: str | None
    observaciones: str | None
    created_at: datetime
