from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CrearReunionInput(BaseModel):
    titulo: str = Field(min_length=3)
    inicio: datetime
    fin: datetime
    participantes_telefonos: list[str] = Field(
        default_factory=list,
        description="Teléfonos WhatsApp de los demás participantes (no incluir el propio).",
    )


class ConsultarCalendarioInput(BaseModel):
    inicio: datetime
    fin: datetime
