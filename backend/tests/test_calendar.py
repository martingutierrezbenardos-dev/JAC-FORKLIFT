from datetime import datetime, timedelta, timezone

import pytest

from app.core.errors import PermissionDeniedError, ValidationDomainError
from app.core.permissions import UserRole
from app.integrations.calendar.google_provider import GoogleCalendarProvider
from app.integrations.calendar.provider import CalendarEvent, CalendarNotConfiguredError
from app.services import calendar_service
from app.tools.registry import get_tool
from tests.conftest import make_user


class _FakeCalendarProvider:
    def __init__(self, available: bool = True) -> None:
        self.available = available
        self.created: list[dict] = []

    def check_availability(self, attendee_emails, start, end) -> bool:
        return self.available

    def create_event(self, title, start, end, attendee_emails) -> CalendarEvent:
        event = CalendarEvent(id="evt-1", title=title, start=start, end=end, attendees=attendee_emails)
        self.created.append({"title": title, "attendees": attendee_emails})
        return event

    def update_event(self, event_id, **changes):
        raise NotImplementedError

    def cancel_event(self, event_id) -> None:
        raise NotImplementedError


def _rango():
    inicio = datetime(2026, 3, 2, 10, 0, tzinfo=timezone.utc)
    return inicio, inicio + timedelta(hours=1)


def test_google_calendar_provider_requiere_configuracion(monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "google_service_account_json", None)

    with pytest.raises(CalendarNotConfiguredError):
        GoogleCalendarProvider(impersonate_email="alguien@jacobea.cl")


def test_gerente_marketing_no_tiene_acceso_a_calendario():
    from app.tools.registry import tools_available_to_role

    tools = {t.name for t in tools_available_to_role(UserRole.GERENTE_MARKETING)}
    assert "crear_reunion" not in tools
    assert "consultar_calendario" not in tools


def test_crear_reunion_sin_permiso(db_session):
    marketing = make_user(db_session, rol=UserRole.GERENTE_MARKETING, telefono="+56900444001", email="m@jacobea.cl")
    inicio, fin = _rango()

    with pytest.raises(PermissionDeniedError):
        calendar_service.crear_reunion(
            db_session, actor=marketing, titulo="Reunión", inicio=inicio, fin=fin,
            participantes_telefonos=[], provider_factory=lambda email: _FakeCalendarProvider(),
        )


def test_crear_reunion_falla_si_actor_no_tiene_email(db_session):
    gerente = make_user(db_session, rol=UserRole.GERENTE_GENERAL, telefono="+56900444002", email=None)
    inicio, fin = _rango()

    with pytest.raises(ValidationDomainError):
        calendar_service.crear_reunion(
            db_session, actor=gerente, titulo="Reunión", inicio=inicio, fin=fin,
            participantes_telefonos=[], provider_factory=lambda email: _FakeCalendarProvider(),
        )


def test_crear_reunion_falla_si_participante_no_tiene_email(db_session):
    gerente = make_user(db_session, rol=UserRole.GERENTE_GENERAL, telefono="+56900444003", email="g@jacobea.cl")
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56900444004", nombre="SinEmail")
    inicio, fin = _rango()

    with pytest.raises(ValidationDomainError):
        calendar_service.crear_reunion(
            db_session, actor=gerente, titulo="Reunión", inicio=inicio, fin=fin,
            participantes_telefonos=[tecnico.telefono_whatsapp],
            provider_factory=lambda email: _FakeCalendarProvider(),
        )


def test_crear_reunion_falla_si_hay_conflicto_de_horario(db_session):
    gerente = make_user(db_session, rol=UserRole.GERENTE_GENERAL, telefono="+56900444005", email="g2@jacobea.cl")
    inicio, fin = _rango()

    with pytest.raises(ValidationDomainError):
        calendar_service.crear_reunion(
            db_session, actor=gerente, titulo="Reunión", inicio=inicio, fin=fin,
            participantes_telefonos=[], provider_factory=lambda email: _FakeCalendarProvider(available=False),
        )


def test_crear_reunion_exitosa(db_session):
    gerente = make_user(db_session, rol=UserRole.GERENTE_GENERAL, telefono="+56900444006", email="g3@jacobea.cl")
    otro = make_user(
        db_session, rol=UserRole.ADMINISTRACION, telefono="+56900444007", nombre="ConEmail", email="otro@jacobea.cl"
    )
    inicio, fin = _rango()
    fake_provider = _FakeCalendarProvider(available=True)

    resultado = calendar_service.crear_reunion(
        db_session, actor=gerente, titulo="Reunión de coordinación", inicio=inicio, fin=fin,
        participantes_telefonos=[otro.telefono_whatsapp], provider_factory=lambda email: fake_provider,
    )

    assert resultado["id"] == "evt-1"
    assert "g3@jacobea.cl" in resultado["participantes"]
    assert "otro@jacobea.cl" in resultado["participantes"]
    assert len(fake_provider.created) == 1


def test_consultar_calendario_devuelve_disponibilidad(db_session):
    gerente = make_user(db_session, rol=UserRole.GERENTE_GENERAL, telefono="+56900444008", email="g4@jacobea.cl")
    inicio, fin = _rango()

    resultado = calendar_service.consultar_calendario(
        db_session, actor=gerente, inicio=inicio, fin=fin,
        provider_factory=lambda email: _FakeCalendarProvider(available=False),
    )

    assert resultado["disponible"] is False


def test_confirmation_level_crear_reunion_depende_de_participantes(db_session):
    from app.schemas.calendar import CrearReunionInput

    gerente = make_user(db_session, rol=UserRole.GERENTE_GENERAL, telefono="+56900444009", email="g5@jacobea.cl")
    tool = get_tool("crear_reunion")

    solo = CrearReunionInput(titulo="Bloqueo personal", inicio=datetime.now(timezone.utc), fin=datetime.now(timezone.utc))
    con_otros = CrearReunionInput(
        titulo="Reunión equipo", inicio=datetime.now(timezone.utc), fin=datetime.now(timezone.utc),
        participantes_telefonos=["+56900000000"],
    )

    assert tool.confirmation_level_for(solo, gerente) == 1
    assert tool.confirmation_level_for(con_otros, gerente) == 2
