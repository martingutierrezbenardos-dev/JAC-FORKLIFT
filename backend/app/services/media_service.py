"""Orquesta la descarga y el procesamiento de archivos multimedia de WhatsApp (Fase 2/4).

No decide qué hacer con el resultado (eso lo hace el webhook / el agente): solo descarga,
transcribe o extrae, sube el archivo a almacenamiento permanente si hay uno configurado, y
deja un registro de auditoría en ``media_logs``.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai.receipt_extraction import ExtractedReceipt, extract_receipt_data
from app.integrations.storage.provider import FileStorageNotConfiguredError
from app.integrations.storage.s3_provider import S3FileStorageProvider
from app.integrations.transcription.provider import OpenAIWhisperTranscriptionProvider
from app.integrations.whatsapp.client import WhatsAppClient
from app.models.media_log import MediaLog, MediaType
from app.models.user import User

logger = logging.getLogger(__name__)

_IMAGE_EXTENSION_BY_MIME = {"image/jpeg": "jpg", "image/png": "png", "image/gif": "gif", "image/webp": "webp"}


@dataclass
class ImageProcessingResult:
    extracted: ExtractedReceipt
    comprobante_url: str | None = None


def _try_store_file(*, user_id, wa_media_id: str, content: bytes, mime_type: str, subfolder: str) -> str | None:
    """Best-effort: si no hay proveedor de almacenamiento configurado, o falla la subida, no
    se interrumpe el procesamiento del mensaje — simplemente no queda una URL permanente."""
    try:
        provider = S3FileStorageProvider()
    except FileStorageNotConfiguredError:
        return None

    extension = _IMAGE_EXTENSION_BY_MIME.get(mime_type.split(";")[0].strip().lower(), "bin")
    key = f"{subfolder}/{user_id}/{wa_media_id}.{extension}"
    try:
        return provider.upload(key, content, mime_type)
    except Exception:  # noqa: BLE001
        logger.exception("No se pudo subir el archivo %s a almacenamiento permanente", wa_media_id)
        return None


def process_audio_message(db: Session, *, user: User, wa_media_id: str) -> str:
    """Descarga y transcribe un audio de WhatsApp. Devuelve el texto transcrito.

    Lanza la excepción del proveedor (p. ej. ``TranscriptionNotConfiguredError``) si algo
    falla — quien llama decide cómo responderle al usuario.
    """
    whatsapp_client = WhatsAppClient()
    audio_bytes, mime_type = whatsapp_client.download_media(wa_media_id)

    log = MediaLog(user_id=user.id, wa_media_id=wa_media_id, media_type=MediaType.AUDIO, mime_type=mime_type)
    try:
        transcript = OpenAIWhisperTranscriptionProvider().transcribe(audio_bytes, mime_type)
        log.transcript = transcript
        db.add(log)
        db.flush()
        return transcript
    except Exception as exc:
        log.error = str(exc)
        db.add(log)
        db.flush()
        raise


def process_image_message(db: Session, *, user: User, wa_media_id: str) -> ImageProcessingResult:
    """Descarga una imagen de WhatsApp, extrae datos de comprobante y la sube a
    almacenamiento permanente si hay un proveedor configurado (Fase 4).

    Lanza la excepción correspondiente (p. ej. ``ReceiptExtractionNotConfiguredError``) si
    falla la extracción. Un fallo al subir el archivo NO se propaga — solo significa que
    ``comprobante_url`` queda en ``None``.
    """
    whatsapp_client = WhatsAppClient()
    image_bytes, mime_type = whatsapp_client.download_media(wa_media_id)

    log = MediaLog(user_id=user.id, wa_media_id=wa_media_id, media_type=MediaType.IMAGE, mime_type=mime_type)
    try:
        extracted = extract_receipt_data(image_bytes, mime_type)
        log.extracted_data = extracted.model_dump(mode="json")
        storage_url = _try_store_file(
            user_id=user.id, wa_media_id=wa_media_id, content=image_bytes, mime_type=mime_type,
            subfolder="comprobantes",
        )
        log.storage_url = storage_url
        db.add(log)
        db.flush()
        return ImageProcessingResult(extracted=extracted, comprobante_url=storage_url)
    except Exception as exc:
        log.error = str(exc)
        db.add(log)
        db.flush()
        raise
