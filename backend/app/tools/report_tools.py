from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models.user import User
from app.services import report_service


class GenerarReporteInput(BaseModel):
    tipo: str = Field(default="gastos", description="'gastos', 'tareas' o 'servicios'.")
    periodo: str | None = Field(
        default=None,
        description="Atajo de período: 'dia', 'semana' (últimos 7 días) o 'mes' (desde el día 1). Ignorado si se dan desde/hasta.",
    )
    desde: date | None = None
    hasta: date | None = None


def generar_reporte(db: Session, actor: User, data: GenerarReporteInput) -> dict:
    if data.tipo == "tareas":
        return report_service.generar_reporte_tareas(db, actor=actor)
    if data.tipo == "servicios":
        return report_service.generar_reporte_servicios(db, actor=actor)

    desde, hasta = report_service.resolve_periodo(data.periodo, data.desde, data.hasta)
    return report_service.generar_reporte_gastos(db, actor=actor, desde=desde, hasta=hasta)
