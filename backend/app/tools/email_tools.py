from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.email import BuscarCorreosInput, EnviarCorreoInput, PrepararCorreoInput
from app.services import email_service


def preparar_correo(db: Session, actor: User, data: PrepararCorreoInput) -> dict:
    return email_service.preparar_correo(
        db,
        actor=actor,
        destinatarios_telefonos=data.destinatarios_telefonos,
        destinatarios_email=data.destinatarios_email,
        asunto=data.asunto,
        cuerpo=data.cuerpo,
        canal="whatsapp",
    )


def enviar_correo(db: Session, actor: User, data: EnviarCorreoInput) -> dict:
    return email_service.enviar_correo(db, actor=actor, draft_id=data.draft_id, canal="whatsapp")


def buscar_correos(db: Session, actor: User, data: BuscarCorreosInput) -> dict:
    return email_service.buscar_correos(db, actor=actor, query=data.query, limite=data.limite)
