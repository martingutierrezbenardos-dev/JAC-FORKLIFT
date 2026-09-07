"""Credenciales compartidas para integraciones de Google Workspace (Calendar, Gmail).

Ambas usan la misma cuenta de servicio con delegación de dominio completo
(``GOOGLE_SERVICE_ACCOUNT_JSON``), pidiendo distintos scopes según la API. Centralizar esto
evita repetir la lógica de carga de credenciales en cada proveedor.
"""
from __future__ import annotations

import json

from app.core.config import get_settings


def build_impersonated_credentials(impersonate_email: str, scopes: list[str]):
    """Construye credenciales de la cuenta de servicio actuando como ``impersonate_email``.

    Lanza ``RuntimeError`` (el llamador la traduce a su propio "not configured error") si
    ``GOOGLE_SERVICE_ACCOUNT_JSON`` no está configurado.
    """
    settings = get_settings()
    if not settings.google_service_account_json:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON no está configurado.")

    from google.oauth2 import service_account

    info = json.loads(settings.google_service_account_json)
    return service_account.Credentials.from_service_account_info(info, scopes=scopes).with_subject(
        impersonate_email
    )
