from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BuscarClienteInput(BaseModel):
    nombre: str = Field(description="Nombre o parte del nombre del cliente a buscar.")


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nombre: str
    rut: str | None
    direccion: str | None
    comuna: str | None
    ciudad: str | None
    contacto: str | None
    telefono: str | None
    email: str | None
    tipo_cliente: str | None
    estado: str
    created_at: datetime
