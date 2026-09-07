"""Implementación REAL de ``EmailProvider`` usando la API de Gmail (sección 14 del brief).

Usa la misma cuenta de servicio con delegación de dominio completo que Google Calendar (ver
``app/integrations/google_workspace.py``), pidiendo los scopes de Gmail. No es un mock: si
``GOOGLE_SERVICE_ACCOUNT_JSON`` no está configurado, o la cuenta de servicio no tiene
delegación para el scope de Gmail, las llamadas fallan con un error real de Google.
"""
from __future__ import annotations

import base64
from email.mime.text import MIMEText

from app.integrations.email.provider import EmailDraft, EmailNotConfiguredError, EmailProvider
from app.integrations.google_workspace import build_impersonated_credentials

_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.send",
]


class GmailEmailProvider(EmailProvider):
    def __init__(self, *, impersonate_email: str) -> None:
        try:
            credentials = build_impersonated_credentials(impersonate_email, _SCOPES)
        except RuntimeError as exc:
            raise EmailNotConfiguredError() from exc

        from googleapiclient.discovery import build

        self._service = build("gmail", "v1", credentials=credentials, cache_discovery=False)

    def search_emails(self, query: str, limit: int = 10) -> list[dict]:
        listing = self._service.users().messages().list(userId="me", q=query, maxResults=limit).execute()
        resultados = []
        for ref in listing.get("messages", []):
            msg = (
                self._service.users()
                .messages()
                .get(userId="me", id=ref["id"], format="metadata", metadataHeaders=["From", "Subject", "Date"])
                .execute()
            )
            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            resultados.append(
                {
                    "id": msg["id"],
                    "de": headers.get("From", ""),
                    "asunto": headers.get("Subject", ""),
                    "fecha": headers.get("Date", ""),
                    "resumen": msg.get("snippet", ""),
                }
            )
        return resultados

    def create_draft(self, draft: EmailDraft) -> str:
        raw = self._encode_message(draft)
        created = self._service.users().drafts().create(userId="me", body={"message": {"raw": raw}}).execute()
        return created["id"]

    def send_draft(self, draft_id: str) -> None:
        self._service.users().drafts().send(userId="me", body={"id": draft_id}).execute()

    @staticmethod
    def _encode_message(draft: EmailDraft) -> str:
        message = MIMEText(draft.body)
        message["To"] = ", ".join(draft.to)
        message["Subject"] = draft.subject
        return base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
