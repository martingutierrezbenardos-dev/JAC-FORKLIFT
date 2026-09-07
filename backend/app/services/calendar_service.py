from __future__ import annotations

from datetime import datetime
from typing import Callable

from sqlalchemy.orm import Session

from app.core.errors import PermissionDeniedError, ValidationDomainError
from app.core.permissions import Permission, has_permission
from app.integrations.calendar.google_provider import GoogleCalendarProvider
from app.integrations.calendar.provider import CalendarNotConfiguredError, CalendarProvider
from app.models.user import User
from app.services import audit_service, user_service

ProviderFactory = Callable[[str], CalendarProvider]


def _default_provider_factory(impersonate_email: str) -> CalendarProvider:
    return GoogleCalendarProvider(impersonate_email=impersonate_email)


def _build_provider(actor: User, provider_factory: ProviderFactory) -> CalendarProvider:
    try:
        return provider_factory(actor.email)
    except CalendarNotConfiguredError as exc:
        raise ValidationDomainError(str(exc)) from exc


def _resolve_attendee_emails(db: Session, telefonos: list[str]) -> list[str]:
    emails = []
    for telefono in telefonos:
        user = user_service.get_by_phone(db, telefono)
        if user is None:
            raise ValidationDomainError(f"No encontré a nadie con el teléfono '{telefono}'.")
        if not user.email:
            raise ValidationDomainError(
                f"{user.nombre_completo} no tiene un email configurado; no se le puede invitar."
            )
        emails.append(user.email)
    return emails


def crear_reunion(
    db: Session,
    *,
    actor: User,
    titulo: str,
    inicio: datetime,
    fin: datetime,
    participantes_telefonos: list[str],
    canal: str = "whatsapp",
    provider_factory: ProviderFactory = _default_provider_factory,
) -> dict:
    if not has_permission(actor.rol, Permission.CALENDAR_USE):
        raise PermissionDeniedError("No tienes permiso para usar el calendario.")
    if not actor.email:
        raise ValidationDomainError(
            "No tienes un email configurado para usar el calendario. Pide a un administrador que lo agregue."
        )
    if fin <= inicio:
        raise ValidationDomainError("La hora de término debe ser posterior a la de inicio.")

    attendee_emails = [actor.email] + _resolve_attendee_emails(db, participantes_telefonos)
    provider = _build_provider(actor, provider_factory)

    if not provider.check_availability(attendee_emails, inicio, fin):
        raise ValidationDomainError(
            "Al menos una persona tiene un conflicto de horario en ese rango. Prueba con otro horario."
        )

    event = provider.create_event(titulo, inicio, fin, attendee_emails)

    audit_service.record(
        db, usuario_id=actor.id, accion="create", entidad="calendar_events", entidad_id=None,
        datos_nuevos={
            "titulo": titulo, "inicio": inicio.isoformat(), "fin": fin.isoformat(),
            "google_event_id": event.id, "participantes": attendee_emails,
        },
        canal=canal,
    )

    return {
        "id": event.id,
        "titulo": event.title,
        "inicio": event.start.isoformat(),
        "fin": event.end.isoformat(),
        "participantes": event.attendees,
    }


def consultar_calendario(
    db: Session,
    *,
    actor: User,
    inicio: datetime,
    fin: datetime,
    provider_factory: ProviderFactory = _default_provider_factory,
) -> dict:
    if not has_permission(actor.rol, Permission.CALENDAR_USE):
        raise PermissionDeniedError("No tienes permiso para usar el calendario.")
    if not actor.email:
        raise ValidationDomainError(
            "No tienes un email configurado para usar el calendario. Pide a un administrador que lo agregue."
        )
    if fin <= inicio:
        raise ValidationDomainError("La hora de término debe ser posterior a la de inicio.")

    provider = _build_provider(actor, provider_factory)
    disponible = provider.check_availability([actor.email], inicio, fin)

    return {"disponible": disponible, "inicio": inicio.isoformat(), "fin": fin.isoformat()}
