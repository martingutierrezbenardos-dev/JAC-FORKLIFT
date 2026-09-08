from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.analytics import CompararPeriodoInput, ResumenEjecutivoInput
from app.services import analytics_service


def comparar_periodo(db: Session, actor: User, data: CompararPeriodoInput) -> dict:
    return analytics_service.comparar_periodos(
        db, actor=actor, tipo=data.tipo, periodo=data.periodo, desde=data.desde, hasta=data.hasta
    )


def generar_resumen_ejecutivo(db: Session, actor: User, data: ResumenEjecutivoInput) -> dict:
    return analytics_service.generar_resumen_ejecutivo(
        db, actor=actor, periodo=data.periodo, desde=data.desde, hasta=data.hasta
    )
