import hashlib
import hmac

import app.api.routes.whatsapp as whatsapp_route
from app.ai.receipt_extraction import ExtractedReceipt, ReceiptExtractionNotConfiguredError
from app.core.config import get_settings
from app.core.permissions import UserRole
from app.integrations.transcription.provider import TranscriptionNotConfiguredError
from app.integrations.whatsapp.client import WhatsAppClient
from tests.conftest import make_user


class _FakeAgent:
    def __init__(self, *args, **kwargs):
        pass

    def handle_message(self, db, user, text):
        return f"echo: {text}"


class _FailIfCalledAgent:
    """Usado en tests donde el agente de IA NO debería llegar a invocarse."""

    def __init__(self, *args, **kwargs):
        pass

    def handle_message(self, db, user, text):
        raise AssertionError("El agente de IA no debería haberse llamado en este escenario.")


class _FakeWhatsAppClient:
    sent: list[tuple[str, str]] = []

    def verify_signature(self, body, header):
        return True

    def send_text(self, to_phone, body):
        _FakeWhatsAppClient.sent.append((to_phone, body))
        return {}


def _webhook_payload(
    from_phone: str,
    message_type: str = "text",
    text_body: str | None = None,
    media_id: str | None = None,
    caption: str | None = None,
) -> dict:
    message = {"from": from_phone, "type": message_type}
    if text_body is not None:
        message["text"] = {"body": text_body}
    if message_type == "audio" and media_id is not None:
        message["audio"] = {"id": media_id}
    if message_type == "image" and media_id is not None:
        message["image"] = {"id": media_id, **({"caption": caption} if caption else {})}
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


def test_webhook_tipo_no_soportado(client, monkeypatch, db_session):
    make_user(db_session, rol=UserRole.TECNICO, telefono="+56977777777")

    monkeypatch.setattr(whatsapp_route, "WhatsAppClient", lambda: _FakeWhatsAppClient())
    _FakeWhatsAppClient.sent.clear()

    response = client.post("/api/whatsapp/webhook", json=_webhook_payload("56977777777", message_type="sticker"))

    assert response.status_code == 200
    assert "audios y fotos de comprobantes" in _FakeWhatsAppClient.sent[0][1]


def test_webhook_audio_se_transcribe_y_pasa_al_agente(client, monkeypatch, db_session):
    make_user(db_session, rol=UserRole.TECNICO, telefono="+56977777701")

    monkeypatch.setattr(whatsapp_route, "WhatsAppClient", lambda: _FakeWhatsAppClient())
    monkeypatch.setattr(whatsapp_route, "AgentSession", _FakeAgent)
    monkeypatch.setattr(
        whatsapp_route.media_service, "process_audio_message",
        lambda db, user, wa_media_id: "gasté 5 mil en peaje",
    )
    _FakeWhatsAppClient.sent.clear()

    response = client.post(
        "/api/whatsapp/webhook",
        json=_webhook_payload("56977777701", message_type="audio", media_id="wamid.audio1"),
    )

    assert response.status_code == 200
    assert _FakeWhatsAppClient.sent == [("+56977777701", "echo: gasté 5 mil en peaje")]


def test_webhook_audio_sin_transcripcion_configurada_responde_directo(client, monkeypatch, db_session):
    make_user(db_session, rol=UserRole.TECNICO, telefono="+56977777702")

    def _raise(db, user, wa_media_id):
        raise TranscriptionNotConfiguredError()

    monkeypatch.setattr(whatsapp_route, "WhatsAppClient", lambda: _FakeWhatsAppClient())
    monkeypatch.setattr(whatsapp_route, "AgentSession", _FailIfCalledAgent)
    monkeypatch.setattr(whatsapp_route.media_service, "process_audio_message", _raise)
    _FakeWhatsAppClient.sent.clear()

    response = client.post(
        "/api/whatsapp/webhook",
        json=_webhook_payload("56977777702", message_type="audio", media_id="wamid.audio2"),
    )

    assert response.status_code == 200
    assert "no puedo transcribir audios" in _FakeWhatsAppClient.sent[0][1]


def test_webhook_imagen_extrae_comprobante_y_pasa_al_agente(client, monkeypatch, db_session):
    make_user(db_session, rol=UserRole.TECNICO, telefono="+56977777703")

    monkeypatch.setattr(whatsapp_route, "WhatsAppClient", lambda: _FakeWhatsAppClient())
    monkeypatch.setattr(whatsapp_route, "AgentSession", _FakeAgent)
    monkeypatch.setattr(
        whatsapp_route.media_service, "process_image_message",
        lambda db, user, wa_media_id: ExtractedReceipt(proveedor="Repuestos X", monto=85000),
    )
    _FakeWhatsAppClient.sent.clear()

    response = client.post(
        "/api/whatsapp/webhook",
        json=_webhook_payload("56977777703", message_type="image", media_id="wamid.img1"),
    )

    assert response.status_code == 200
    body = _FakeWhatsAppClient.sent[0][1]
    assert "proveedor=Repuestos X" in body
    assert "monto=85000" in body


def test_webhook_imagen_sin_extraccion_configurada_responde_directo(client, monkeypatch, db_session):
    make_user(db_session, rol=UserRole.TECNICO, telefono="+56977777704")

    def _raise(db, user, wa_media_id):
        raise ReceiptExtractionNotConfiguredError()

    monkeypatch.setattr(whatsapp_route, "WhatsAppClient", lambda: _FakeWhatsAppClient())
    monkeypatch.setattr(whatsapp_route, "AgentSession", _FailIfCalledAgent)
    monkeypatch.setattr(whatsapp_route.media_service, "process_image_message", _raise)
    _FakeWhatsAppClient.sent.clear()

    response = client.post(
        "/api/whatsapp/webhook",
        json=_webhook_payload("56977777704", message_type="image", media_id="wamid.img2"),
    )

    assert response.status_code == 200
    assert "no puedo leer comprobantes automáticamente" in _FakeWhatsAppClient.sent[0][1]


def test_verify_signature_valid_and_invalid(monkeypatch):
    ws_client = WhatsAppClient()
    monkeypatch.setattr(ws_client._settings, "whatsapp_app_secret", "shh")
    monkeypatch.setattr(ws_client._settings, "environment", "production")  # fuerza validación estricta

    body = b'{"a":1}'
    valid_signature = "sha256=" + hmac.new(b"shh", body, hashlib.sha256).hexdigest()

    assert ws_client.verify_signature(body, valid_signature) is True
    assert ws_client.verify_signature(body, "sha256=deadbeef") is False
    assert ws_client.verify_signature(body, None) is False
