"""Interfaz abstracta para integración de correo (sección 14 del brief).

Implementación real en ``app/integrations/email/gmail_provider.py`` (Fase 4). Por diseño de
seguridad, "enviar" es siempre una acción de nivel 2 en el agente de IA (requiere confirmación
explícita del usuario) — nunca se debe enviar un correo externo sin que la persona lo confirme
(ver ``app/tools/registry.py::REGISTRY["enviar_correo"]``).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class EmailDraft:
    to: list[str]
    subject: str
    body: str


class EmailProvider(ABC):
    @abstractmethod
    def search_emails(self, query: str, limit: int = 10) -> list[dict]: ...

    @abstractmethod
    def create_draft(self, draft: EmailDraft) -> str:
        """Crea un borrador y devuelve su id. No envía nada."""

    @abstractmethod
    def send_draft(self, draft_id: str) -> None:
        """Envía un borrador ya creado. Debe invocarse solo tras confirmación explícita del usuario."""


class EmailNotConfiguredError(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "La integración de correo (Gmail/Outlook) aún no está configurada (planificada "
            "para la Fase 4, ver docs/architecture.md)."
        )
