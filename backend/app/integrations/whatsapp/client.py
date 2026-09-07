"""Cliente REAL de la WhatsApp Business Cloud API (Meta).

No es un mock: llama al endpoint oficial de Graph API. Para probarlo de punta a punta se
necesitan credenciales reales en `.env` (ver docs/whatsapp.md). En los tests unitarios se
mockea `httpx.Client.post`.
"""
from __future__ import annotations

import hashlib
import hmac
import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class WhatsAppConfigurationError(RuntimeError):
    pass


class WhatsAppClient:
    def __init__(self) -> None:
        self._settings = get_settings()

    @property
    def _base_url(self) -> str:
        return f"https://graph.facebook.com/{self._settings.whatsapp_api_version}"

    def _require_credentials(self) -> tuple[str, str]:
        phone_number_id = self._settings.whatsapp_phone_number_id
        access_token = self._settings.whatsapp_access_token
        if not phone_number_id or not access_token:
            raise WhatsAppConfigurationError(
                "WHATSAPP_PHONE_NUMBER_ID / WHATSAPP_ACCESS_TOKEN no están configurados. "
                "Ver docs/whatsapp.md para configurar la Cloud API."
            )
        return phone_number_id, access_token

    def send_text(self, to_phone: str, body: str) -> dict:
        """Envía un mensaje de texto de formato libre. Solo válido dentro de la ventana de
        24 horas desde el último mensaje del usuario (regla de Meta)."""
        phone_number_id, access_token = self._require_credentials()
        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "text",
            "text": {"body": body},
        }
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                f"{self._base_url}/{phone_number_id}/messages",
                json=payload,
                headers={"Authorization": f"Bearer {access_token}"},
            )
        response.raise_for_status()
        return response.json()

    def send_template(self, to_phone: str, template_name: str, language_code: str = "es") -> dict:
        """Placeholder documentado: envío de plantillas pre-aprobadas para mensajes
        proactivos (fuera de la ventana de 24h). No se usa en Fase 1 — ver docs/whatsapp.md.
        """
        phone_number_id, access_token = self._require_credentials()
        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "template",
            "template": {"name": template_name, "language": {"code": language_code}},
        }
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                f"{self._base_url}/{phone_number_id}/messages",
                json=payload,
                headers={"Authorization": f"Bearer {access_token}"},
            )
        response.raise_for_status()
        return response.json()

    def verify_signature(self, payload_body: bytes, signature_header: str | None) -> bool:
        """Valida X-Hub-Signature-256 usando WHATSAPP_APP_SECRET (HMAC-SHA256)."""
        if not self._settings.whatsapp_app_secret:
            logger.warning("WHATSAPP_APP_SECRET no configurado: firma del webhook no verificada.")
            return not self._settings.is_production
        if not signature_header or not signature_header.startswith("sha256="):
            return False
        expected = hmac.new(
            self._settings.whatsapp_app_secret.encode("utf-8"), payload_body, hashlib.sha256
        ).hexdigest()
        provided = signature_header.removeprefix("sha256=")
        return hmac.compare_digest(expected, provided)
