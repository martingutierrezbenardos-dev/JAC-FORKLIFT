"""Orquesta la descarga y el procesamiento de archivos multimedia de WhatsApp (Fase 2).

No decide qué hacer con el resultado (eso lo hace el webhook / el agente): solo descarga,
transcribe o extrae, y deja un registro de auditoría en ``media_logs``.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.receipt_extraction import ExtractedReceipt, extract_receipt_data
from app.integrations.transcription.provider import OpenAIWhisperTranscriptionProvider
from app.integrations.whatsapp.client import WhatsAppClient
from app.models.media_log import MediaLog, MediaType
from app.models.user import User


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


def process_image_message(db: Session, *, user: User, wa_media_id: str) -> ExtractedReceipt:
    """Descarga una imagen de WhatsApp y extrae datos de comprobante desde ella.

    Lanza la excepción correspondiente (p. ej. ``ReceiptExtractionNotConfiguredError``) si
    algo falla.
    """
    whatsapp_client = WhatsAppClient()
    image_bytes, mime_type = whatsapp_client.download_media(wa_media_id)

    log = MediaLog(user_id=user.id, wa_media_id=wa_media_id, media_type=MediaType.IMAGE, mime_type=mime_type)
    try:
        extracted = extract_receipt_data(image_bytes, mime_type)
        log.extracted_data = extracted.model_dump(mode="json")
        db.add(log)
        db.flush()
        return extracted
    except Exception as exc:
        log.error = str(exc)
        db.add(log)
        db.flush()
        raise
