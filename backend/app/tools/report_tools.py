from __future__ import annotations

from datetime import date

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.user import User
from app.services import report_service


class GenerarReporteInput(BaseModel):
    tipo: str = "gastos"  # "gastos" | "tareas"
    desde: date | None = None
    hasta: date | None = None


def generar_reporte(db: Session, actor: User, data: GenerarReporteInput) -> dict:
    if data.tipo == "tareas":
        return report_service.generar_reporte_tareas(db, actor=actor)
    return report_service.generar_reporte_gastos(db, actor=actor, desde=data.desde, hasta=data.hasta)
