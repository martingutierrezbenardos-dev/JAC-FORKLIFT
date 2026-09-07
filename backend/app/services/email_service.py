from __future__ import annotations

from typing import Callable

from sqlalchemy.orm import Session

from app.core.errors import PermissionDeniedError, ValidationDomainError
from app.core.permissions import Permission, has_permission
from app.integrations.email.gmail_provider import GmailEmailProvider
from app.integrations.email.provider import EmailDraft, EmailNotConfiguredError, EmailProvider
from app.models.user import User
from app.services import audit_service, user_service

ProviderFactory = Callable[[str], EmailProvider]


def _default_provider_factory(impersonate_email: str) -> EmailProvider:
    return GmailEmailProvider(impersonate_email=impersonate_email)


def _build_provider(actor: User, provider_factory: ProviderFactory) -> EmailProvider:
    try:
        return provider_factory(actor.email)
    except EmailNotConfiguredError as exc:
        raise ValidationDomainError(str(exc)) from exc


def _require_actor_email(actor: User) -> None:
    if not actor.email:
        raise ValidationDomainError(
            "No tienes un email configurado para usar el correo. Pide a un administrador que lo agregue."
        )


def _resolve_recipient_emails(
    db: Session, *, destinatarios_telefonos: list[str], destinatarios_email: list[str]
) -> list[str]:
    resolved = list(destinatarios_email)
    for telefono in destinatarios_telefonos:
        user = user_service.get_by_phone(db, telefono)
        if user is None:
            raise ValidationDomainError(f"No encontré a nadie con el teléfono '{telefono}'.")
        if not user.email:
            raise ValidationDomainError(f"{user.nombre_completo} no tiene un email configurado.")
        resolved.append(user.email)

    if not resolved:
        raise ValidationDomainError("Necesito al menos un destinatario (teléfono o email).")
    return resolved


def preparar_correo(
    db: Session,
    *,
    actor: User,
    destinatarios_telefonos: list[str],
    destinatarios_email: list[str],
    asunto: str,
    cuerpo: str,
    canal: str = "whatsapp",
    provider_factory: ProviderFactory = _default_provider_factory,
) -> dict:
    if not has_permission(actor.rol, Permission.EMAIL_USE):
        raise PermissionDeniedError("No tienes permiso para usar el correo.")
    _require_actor_email(actor)

    destinatarios = _resolve_recipient_emails(
        db, destinatarios_telefonos=destinatarios_telefonos, destinatarios_email=destinatarios_email
    )
    provider = _build_provider(actor, provider_factory)
    draft_id = provider.create_draft(EmailDraft(to=destinatarios, subject=asunto, body=cuerpo))

    audit_service.record(
        db, usuario_id=actor.id, accion="create", entidad="email_drafts", entidad_id=None,
        datos_nuevos={"draft_id": draft_id, "destinatarios": destinatarios, "asunto": asunto},
        canal=canal,
    )
    return {"draft_id": draft_id, "destinatarios": destinatarios, "asunto": asunto, "enviado": False}


def enviar_correo(
    db: Session,
    *,
    actor: User,
    draft_id: str,
    canal: str = "whatsapp",
    provider_factory: ProviderFactory = _default_provider_factory,
) -> dict:
    if not has_permission(actor.rol, Permission.EMAIL_USE):
        raise PermissionDeniedError("No tienes permiso para usar el correo.")
    _require_actor_email(actor)

    provider = _build_provider(actor, provider_factory)
    provider.send_draft(draft_id)

    audit_service.record(
        db, usuario_id=actor.id, accion="send", entidad="email_drafts", entidad_id=None,
        datos_nuevos={"draft_id": draft_id}, canal=canal,
    )
    return {"draft_id": draft_id, "enviado": True}


def buscar_correos(
    db: Session,
    *,
    actor: User,
    query: str,
    limite: int = 10,
    provider_factory: ProviderFactory = _default_provider_factory,
) -> dict:
    if not has_permission(actor.rol, Permission.EMAIL_USE):
        raise PermissionDeniedError("No tienes permiso para usar el correo.")
    _require_actor_email(actor)

    provider = _build_provider(actor, provider_factory)
    resultados = provider.search_emails(query, limite)
    return {"cantidad": len(resultados), "correos": resultados}
