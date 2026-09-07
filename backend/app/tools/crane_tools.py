from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.crane import ConsultarHorasGruaInput, RegistrarUsoGruaInput
from app.services import crane_service


def registrar_uso_grua(db: Session, actor: User, data: RegistrarUsoGruaInput) -> dict:
    return crane_service.registrar_uso_grua(
        db, actor=actor, cliente_nombre=data.cliente_nombre, horas_usadas=data.horas_usadas,
        fecha=data.fecha, observaciones=data.observaciones, canal="whatsapp",
    )


def consultar_horas_grua(db: Session, actor: User, data: ConsultarHorasGruaInput) -> dict:
    return crane_service.consultar_horas_grua(db, actor=actor, cliente_nombre=data.cliente_nombre)
