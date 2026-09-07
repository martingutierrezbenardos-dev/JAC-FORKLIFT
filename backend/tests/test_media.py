import pytest
from sqlalchemy import select

import app.services.media_service as media_service_module
from app.ai.receipt_extraction import ExtractedReceipt, UnsupportedImageTypeError, extract_receipt_data
from app.core.config import get_settings
from app.core.permissions import UserRole
from app.integrations.transcription.provider import (
    OpenAIWhisperTranscriptionProvider,
    TranscriptionNotConfiguredError,
)
from app.models.media_log import MediaLog, MediaType
from app.services import media_service
from tests.conftest import make_user


def test_transcription_provider_requires_api_key(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", None)

    with pytest.raises(TranscriptionNotConfiguredError):
        OpenAIWhisperTranscriptionProvider()


class _FakeTextBlock:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _FakeAnthropicResponse:
    def __init__(self, text: str) -> None:
        self.content = [_FakeTextBlock(text)]


class _FakeAnthropicMessages:
    def __init__(self, response_text: str) -> None:
        self._response_text = response_text

    def create(self, **kwargs):
        return _FakeAnthropicResponse(self._response_text)


class _FakeAnthropicClient:
    def __init__(self, response_text: str) -> None:
        self.messages = _FakeAnthropicMessages(response_text)


def test_extract_receipt_data_parses_json_response():
    fake_client = _FakeAnthropicClient(
        '{"proveedor": "Repuestos X", "fecha": "2026-01-15", "monto": 85000, "moneda": "CLP", '
        '"numero_documento": "1234", "productos": ["rodamiento"], "impuestos": null, "nota": null}'
    )

    result = extract_receipt_data(b"fake-image-bytes", "image/jpeg", client=fake_client)

    assert isinstance(result, ExtractedReceipt)
    assert result.proveedor == "Repuestos X"
    assert result.monto == 85000
    assert result.productos == ["rodamiento"]


def test_extract_receipt_data_never_invents_missing_fields():
    fake_client = _FakeAnthropicClient(
        '{"proveedor": null, "fecha": null, "monto": null, "moneda": null, '
        '"numero_documento": null, "productos": [], "impuestos": null, "nota": "imagen borrosa"}'
    )

    result = extract_receipt_data(b"fake-image-bytes", "image/jpeg", client=fake_client)

    assert result.proveedor is None
    assert result.monto is None
    assert result.nota == "imagen borrosa"


def test_extract_receipt_data_handles_malformed_response_gracefully():
    fake_client = _FakeAnthropicClient("esto no es json")

    result = extract_receipt_data(b"fake-image-bytes", "image/jpeg", client=fake_client)

    assert result.proveedor is None
    assert result.nota is not None


def test_extract_receipt_data_rejects_unsupported_mime_type():
    with pytest.raises(UnsupportedImageTypeError):
        extract_receipt_data(b"...", "application/pdf", client=_FakeAnthropicClient("{}"))


def test_media_service_process_audio_logs_transcript(db_session, monkeypatch):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56988888801")

    monkeypatch.setattr(
        media_service_module.WhatsAppClient, "download_media",
        lambda self, media_id: (b"audio-bytes", "audio/ogg"),
    )

    class _FakeTranscriptionProvider:
        def transcribe(self, audio_bytes, mime_type):
            return "hola esto es una prueba"

    monkeypatch.setattr(media_service_module, "OpenAIWhisperTranscriptionProvider", _FakeTranscriptionProvider)

    transcript = media_service.process_audio_message(db_session, user=tecnico, wa_media_id="wamid.123")

    assert transcript == "hola esto es una prueba"
    log = db_session.execute(select(MediaLog).where(MediaLog.wa_media_id == "wamid.123")).scalars().first()
    assert log is not None
    assert log.media_type == MediaType.AUDIO
    assert log.transcript == "hola esto es una prueba"


def test_media_service_process_audio_logs_error_when_transcription_fails(db_session, monkeypatch):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56988888803")

    monkeypatch.setattr(
        media_service_module.WhatsAppClient, "download_media",
        lambda self, media_id: (b"audio-bytes", "audio/ogg"),
    )

    def _raise(*args, **kwargs):
        raise TranscriptionNotConfiguredError()

    monkeypatch.setattr(media_service_module, "OpenAIWhisperTranscriptionProvider", _raise)

    with pytest.raises(TranscriptionNotConfiguredError):
        media_service.process_audio_message(db_session, user=tecnico, wa_media_id="wamid.999")

    log = db_session.execute(select(MediaLog).where(MediaLog.wa_media_id == "wamid.999")).scalars().first()
    assert log is not None
    assert log.error is not None
    assert log.transcript is None


def test_media_service_process_image_logs_extraction(db_session, monkeypatch):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56988888802")

    monkeypatch.setattr(
        media_service_module.WhatsAppClient, "download_media",
        lambda self, media_id: (b"image-bytes", "image/jpeg"),
    )
    monkeypatch.setattr(
        media_service_module, "extract_receipt_data",
        lambda image_bytes, mime_type: ExtractedReceipt(proveedor="Repuestos Y", monto=15000),
    )

    result = media_service.process_image_message(db_session, user=tecnico, wa_media_id="wamid.456")

    assert result.extracted.proveedor == "Repuestos Y"
    assert result.comprobante_url is None  # sin AWS_S3_BUCKET configurado, no se sube el archivo
    log = db_session.execute(select(MediaLog).where(MediaLog.wa_media_id == "wamid.456")).scalars().first()
    assert log is not None
    assert log.media_type == MediaType.IMAGE
    assert log.extracted_data["proveedor"] == "Repuestos Y"
