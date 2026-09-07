from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services import report_service

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/gastos")
def reporte_gastos(
    desde: date | None = None,
    hasta: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return report_service.generar_reporte_gastos(db, actor=current_user, desde=desde, hasta=hasta)


@router.get("/tareas")
def reporte_tareas(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return report_service.generar_reporte_tareas(db, actor=current_user)
