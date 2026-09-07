import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.ai.agent import AgentSession
from app.ai.receipt_extraction import (
    ExtractedReceipt,
    ReceiptExtractionNotConfiguredError,
    UnsupportedImageTypeError,
)
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.integrations.transcription.provider import TranscriptionNotConfiguredError
from app.integrations.whatsapp.client import WhatsAppClient
from app.services import media_service, user_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])
settings = get_settings()

_UNSUPPORTED_MESSAGE = (
    "Por ahora solo puedo procesar mensajes de texto, audios y fotos de comprobantes. Ese "
    "tipo de archivo todavía no lo puedo leer 🙂"
)
_UNKNOWN_USER_MESSAGE = (
    "Tu número no está registrado en Jacobea AI. Pide a un administrador que te agregue."
)


class _DirectReply(Exception):
    """Señal interna: responder directamente sin pasar por el agente de IA."""

    def __init__(self, text: str) -> None:
        self.text = text


def _normalize_phone(raw_phone: str) -> str:
    return raw_phone if raw_phone.startswith("+") else f"+{raw_phone}"


@router.get("/webhook")
def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
) -> Response:
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        return Response(content=hub_challenge, media_type="text/plain")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verify token inválido.")


@router.post("/webhook")
@limiter.limit(settings.rate_limit_webhook)
async def receive_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    raw_body = await request.body()
    whatsapp_client = WhatsAppClient()

    signature = request.headers.get("X-Hub-Signature-256")
    if not whatsapp_client.verify_signature(raw_body, signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Firma de webhook inválida.")

    payload = await request.json()
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for message in value.get("messages", []):
                _handle_inbound_message(db, whatsapp_client, message)

    return {"status": "ok"}


def _handle_inbound_message(db: Session, whatsapp_client: WhatsAppClient, message: dict) -> None:
    from_phone = _normalize_phone(message.get("from", ""))
    message_type = message.get("type")

    user = user_service.get_by_phone(db, from_phone)
    if user is None or not user.activo:
        logger.info("Mensaje de WhatsApp de número no registrado: %s", from_phone)
        _safe_reply(whatsapp_client, from_phone, _UNKNOWN_USER_MESSAGE)
        return

    try:
        text_for_agent = _resolve_message_text(db, user, message, message_type)
    except _DirectReply as direct:
        _safe_reply(whatsapp_client, from_phone, direct.text)
        return

    if not text_for_agent:
        return

    try:
        agent = AgentSession()
        reply = agent.handle_message(db, user, text_for_agent)
        db.commit()
    except Exception:  # noqa: BLE001 — no queremos que un error del agente tumbe el webhook
        db.rollback()
        logger.exception("Error procesando mensaje de WhatsApp de %s", from_phone)
        reply = "Tuve un problema procesando tu mensaje. Intenta de nuevo en unos minutos."

    _safe_reply(whatsapp_client, from_phone, reply)


def _resolve_message_text(db: Session, user, message: dict, message_type: str | None) -> str | None:
    """Convierte el mensaje entrante (texto, audio o imagen) en el texto que se le pasa al
    agente de IA, o lanza ``_DirectReply`` si hay que responder sin pasar por el agente
    (tipo no soportado, o un error al procesar el archivo)."""
    if message_type == "text":
        text = message.get("text", {}).get("body", "").strip()
        return text or None

    if message_type == "audio":
        return _resolve_audio_message(db, user, message)

    if message_type == "image":
        return _resolve_image_message(db, user, message)

    raise _DirectReply(_UNSUPPORTED_MESSAGE)


def _resolve_audio_message(db: Session, user, message: dict) -> str:
    media_id = message.get("audio", {}).get("id")
    if not media_id:
        raise _DirectReply("No pude leer ese audio.")

    try:
        transcript = media_service.process_audio_message(db, user=user, wa_media_id=media_id)
        db.commit()
    except TranscriptionNotConfiguredError:
        db.rollback()
        raise _DirectReply(
            "Por ahora no puedo transcribir audios (falta configurar el servicio de "
            "transcripción). ¿Puedes escribirlo como texto mientras tanto?"
        )
    except Exception:
        db.rollback()
        logger.exception("Error transcribiendo audio de %s", user.telefono_whatsapp)
        raise _DirectReply("No pude transcribir ese audio. ¿Puedes escribirlo como texto?")

    if not transcript:
        raise _DirectReply("No logré entender el audio. ¿Puedes intentar de nuevo o escribirlo?")
    return transcript


def _resolve_image_message(db: Session, user, message: dict) -> str:
    image_payload = message.get("image", {})
    media_id = image_payload.get("id")
    caption = (image_payload.get("caption") or "").strip()
    if not media_id:
        raise _DirectReply("No pude leer esa imagen.")

    try:
        extracted = media_service.process_image_message(db, user=user, wa_media_id=media_id)
        db.commit()
    except ReceiptExtractionNotConfiguredError:
        db.rollback()
        raise _DirectReply(
            "Por ahora no puedo leer comprobantes automáticamente (falta configurar esto). "
            "Cuéntame los datos del gasto por texto y lo registro igual."
        )
    except UnsupportedImageTypeError:
        db.rollback()
        raise _DirectReply("No pude leer ese formato de imagen. ¿Puedes enviarla como JPG o PNG?")
    except Exception:
        db.rollback()
        logger.exception("Error extrayendo datos de comprobante de %s", user.telefono_whatsapp)
        raise _DirectReply("No pude leer ese comprobante. Cuéntame los datos por texto y lo registro.")

    return _compose_receipt_message(caption, extracted)


def _compose_receipt_message(caption: str, extracted: ExtractedReceipt) -> str:
    datos = extracted.model_dump(exclude_none=True, exclude_defaults=True, exclude={"nota"})
    detalle = ", ".join(f"{k}={v}" for k, v in datos.items()) or "no se pudo leer ningún dato con certeza"
    partes = [f"[Comprobante recibido. Datos detectados automáticamente en la foto: {detalle}.]"]
    if extracted.nota:
        partes.append(f"[Nota de la lectura automática: {extracted.nota}]")
    partes.append(
        caption
        or "Registra el gasto con estos datos; pregúntame si falta algo que no puedas leer de la foto (como la categoría)."
    )
    return "\n".join(partes)


def _safe_reply(whatsapp_client: WhatsAppClient, to_phone: str, body: str) -> None:
    try:
        whatsapp_client.send_text(to_phone, body)
    except Exception:  # noqa: BLE001
        logger.exception("No se pudo enviar respuesta de WhatsApp a %s", to_phone)
