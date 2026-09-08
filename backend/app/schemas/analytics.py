from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class CompararPeriodoInput(BaseModel):
    tipo: str = Field(default="gastos", description="'gastos', 'servicios' o 'tareas'.")
    periodo: str | None = Field(
        default="mes",
        description="Atajo de período: 'dia', 'semana' (últimos 7 días) o 'mes' (desde el día 1). Ignorado si se dan desde/hasta.",
    )
    desde: date | None = None
    hasta: date | None = None


class ResumenEjecutivoInput(BaseModel):
    periodo: str | None = Field(
        default="mes",
        description="Atajo de período: 'dia', 'semana' o 'mes' (default). Ignorado si se dan desde/hasta.",
    )
    desde: date | None = None
    hasta: date | None = None
