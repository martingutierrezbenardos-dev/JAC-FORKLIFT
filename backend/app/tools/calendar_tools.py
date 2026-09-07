from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.calendar import ConsultarCalendarioInput, CrearReunionInput
from app.services import calendar_service


def crear_reunion(db: Session, actor: User, data: CrearReunionInput) -> dict:
    return calendar_service.crear_reunion(
        db,
        actor=actor,
        titulo=data.titulo,
        inicio=data.inicio,
        fin=data.fin,
        participantes_telefonos=data.participantes_telefonos,
        canal="whatsapp",
    )


def consultar_calendario(db: Session, actor: User, data: ConsultarCalendarioInput) -> dict:
    return calendar_service.consultar_calendario(db, actor=actor, inicio=data.inicio, fin=data.fin)
