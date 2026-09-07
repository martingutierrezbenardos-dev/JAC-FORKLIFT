"""Implementación REAL de ``CalendarProvider`` usando Google Calendar (sección 13 del brief).

Usa una cuenta de servicio de Google Workspace con **delegación de dominio completo**
(domain-wide delegation): un administrador de Google Workspace debe autorizar el ID de
cliente de la cuenta de servicio con el scope
``https://www.googleapis.com/auth/calendar`` en la consola de administración. Esto permite
que el backend actúe "como si fuera" cada usuario (``with_subject(email)``), sin pedirle a
cada persona que autorice individualmente con OAuth.

No es un mock: si ``GOOGLE_SERVICE_ACCOUNT_JSON`` no está configurado, o el email de la
persona no tiene delegación válida, las llamadas fallan con un error real de Google — nunca
se devuelve una disponibilidad o un evento simulado.
"""
from __future__ import annotations

import json
from datetime import datetime

from app.core.config import get_settings
from app.integrations.calendar.provider import CalendarEvent, CalendarNotConfiguredError, CalendarProvider

_SCOPES = ["https://www.googleapis.com/auth/calendar"]


class GoogleCalendarProvider(CalendarProvider):
    def __init__(self, *, impersonate_email: str, calendar_id: str = "primary") -> None:
        settings = get_settings()
        if not settings.google_service_account_json:
            raise CalendarNotConfiguredError()

        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        info = json.loads(settings.google_service_account_json)
        credentials = service_account.Credentials.from_service_account_info(
            info, scopes=_SCOPES
        ).with_subject(impersonate_email)

        self._service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
        self._calendar_id = calendar_id

    def check_availability(self, attendee_emails: list[str], start: datetime, end: datetime) -> bool:
        body = {
            "timeMin": start.isoformat(),
            "timeMax": end.isoformat(),
            "items": [{"id": email} for email in attendee_emails],
        }
        response = self._service.freebusy().query(body=body).execute()
        return all(not cal.get("busy") for cal in response.get("calendars", {}).values())

    def create_event(
        self, title: str, start: datetime, end: datetime, attendee_emails: list[str]
    ) -> CalendarEvent:
        body = {
            "summary": title,
            "start": {"dateTime": start.isoformat()},
            "end": {"dateTime": end.isoformat()},
            "attendees": [{"email": email} for email in attendee_emails],
        }
        created = (
            self._service.events()
            .insert(calendarId=self._calendar_id, body=body, sendUpdates="all")
            .execute()
        )
        return CalendarEvent(id=created["id"], title=title, start=start, end=end, attendees=attendee_emails)

    def update_event(self, event_id: str, **changes) -> CalendarEvent:
        event = self._service.events().get(calendarId=self._calendar_id, eventId=event_id).execute()
        if "title" in changes:
            event["summary"] = changes["title"]
        if "start" in changes:
            event["start"] = {"dateTime": changes["start"].isoformat()}
        if "end" in changes:
            event["end"] = {"dateTime": changes["end"].isoformat()}

        updated = (
            self._service.events()
            .update(calendarId=self._calendar_id, eventId=event_id, body=event, sendUpdates="all")
            .execute()
        )
        return CalendarEvent(
            id=updated["id"],
            title=updated.get("summary", ""),
            start=datetime.fromisoformat(updated["start"]["dateTime"]),
            end=datetime.fromisoformat(updated["end"]["dateTime"]),
            attendees=[a["email"] for a in updated.get("attendees", [])],
        )

    def cancel_event(self, event_id: str) -> None:
        self._service.events().delete(
            calendarId=self._calendar_id, eventId=event_id, sendUpdates="all"
        ).execute()
