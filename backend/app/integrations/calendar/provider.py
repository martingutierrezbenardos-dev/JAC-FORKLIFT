"""Interfaz abstracta para integración de calendario (sección 13 del brief, Fase 3).

No implementado en Fase 1: requiere credenciales OAuth de Google Workspace que la empresa
aún no ha configurado. Ninguna tool de IA usa esta interfaz todavía.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class CalendarEvent:
    id: str
    title: str
    start: datetime
    end: datetime
    attendees: list[str]


class CalendarProvider(ABC):
    @abstractmethod
    def check_availability(self, attendee_emails: list[str], start: datetime, end: datetime) -> bool: ...

    @abstractmethod
    def create_event(
        self, title: str, start: datetime, end: datetime, attendee_emails: list[str]
    ) -> CalendarEvent: ...

    @abstractmethod
    def update_event(self, event_id: str, **changes) -> CalendarEvent: ...

    @abstractmethod
    def cancel_event(self, event_id: str) -> None: ...


class CalendarNotConfiguredError(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "La integración con Google Calendar aún no está configurada (planificada para "
            "la Fase 3, ver docs/architecture.md)."
        )
