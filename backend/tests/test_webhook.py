import hashlib
import hmac

import app.api.routes.whatsapp as whatsapp_route
from app.core.config import get_settings
from app.core.permissions import UserRole
from app.integrations.whatsapp.client import WhatsAppClient
from tests.conftest import make_user


class _FakeAgent:
    def __init__(self, *args, **kwargs):
        pass

    def handle_message(self, db, user, text):
        return f"echo: {text}"


class _FakeWhatsAppClient:
    sent: list[tuple[str, str]] = []

    def verify_signature(self, body, header):
        return True

    def send_text(self, to_phone, body):
        _FakeWhatsAppClient.sent.append((to_phone, body))
        return {}


def _webhook_payload(from_phone: str, message_type: str = "text", text_body: str | None = None) -> dict:
    message = {"from": from_phone, "type": message_type}
    if text_body is not None:
        message["text"] = {"body": text_body}
    return {"entry": [{"changes": [{"value": {"messages": [message]}}]}]}


def test_verify_webhook_ok(client):
    settings = get_settings()
    settings.whatsapp_verify_token = "mi-verify-token"

    response = client.get(
        "/api/whatsapp/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": "mi-verify-token", "hub.challenge": "12345"},
    )

    assert response.status_code == 200
    assert response.text == "12345"


def test_verify_webhook_wrong_token(client):
    settings = get_settings()
    settings.whatsapp_verify_token = "correcto"

    response = client.get(
        "/api/whatsapp/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": "incorrecto", "hub.challenge": "12345"},
    )

    assert response.status_code == 403


def test_webhook_numero_no_registrado_no_llama_al_agente(client, monkeypatch, db_session):
    monkeypatch.setattr(whatsapp_route, "WhatsAppClient", lambda: _FakeWhatsAppClient())
    _FakeWhatsAppClient.sent.clear()

    response = client.post("/api/whatsapp/webhook", json=_webhook_payload("56999999999", text_body="hola"))

    assert response.status_code == 200
    assert len(_FakeWhatsAppClient.sent) == 1
    to_phone, body = _FakeWhatsAppClient.sent[0]
    assert to_phone == "+56999999999"
    assert "no está registrado" in body


def test_webhook_usuario_registrado_llama_al_agente(client, monkeypatch, db_session):
    make_user(db_session, rol=UserRole.TECNICO, telefono="+56988888888")

    monkeypatch.setattr(whatsapp_route, "WhatsAppClient", lambda: _FakeWhatsAppClient())
    monkeypatch.setattr(whatsapp_route, "AgentSession", _FakeAgent)
    _FakeWhatsAppClient.sent.clear()

    response = client.post("/api/whatsapp/webhook", json=_webhook_payload("56988888888", text_body="hola bot"))

    assert response.status_code == 200
    assert _FakeWhatsAppClient.sent == [("+56988888888", "echo: hola bot")]


def test_webhook_audio_no_soportado_en_fase_1(client, monkeypatch, db_session):
    make_user(db_session, rol=UserRole.TECNICO, telefono="+56977777777")

    monkeypatch.setattr(whatsapp_route, "WhatsAppClient", lambda: _FakeWhatsAppClient())
    _FakeWhatsAppClient.sent.clear()

    response = client.post("/api/whatsapp/webhook", json=_webhook_payload("56977777777", message_type="audio"))

    assert response.status_code == 200
    assert "solo puedo procesar mensajes de texto" in _FakeWhatsAppClient.sent[0][1]


def test_verify_signature_valid_and_invalid(monkeypatch):
    ws_client = WhatsAppClient()
    monkeypatch.setattr(ws_client._settings, "whatsapp_app_secret", "shh")
    monkeypatch.setattr(ws_client._settings, "environment", "production")  # fuerza validación estricta

    body = b'{"a":1}'
    valid_signature = "sha256=" + hmac.new(b"shh", body, hashlib.sha256).hexdigest()

    assert ws_client.verify_signature(body, valid_signature) is True
    assert ws_client.verify_signature(body, "sha256=deadbeef") is False
    assert ws_client.verify_signature(body, None) is False
