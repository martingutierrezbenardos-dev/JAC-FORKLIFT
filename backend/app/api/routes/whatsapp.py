import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.ai.agent import AgentSession
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.integrations.whatsapp.client import WhatsAppClient
from app.services import user_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])
settings = get_settings()

_UNSUPPORTED_MESSAGE = (
    "Por ahora solo puedo procesar mensajes de texto. Pronto voy a poder escuchar audios y "
    "leer comprobantes 🙂"
)
_UNKNOWN_USER_MESSAGE = (
    "Tu número no está registrado en Jacobea AI. Pide a un administrador que te agregue."
)


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

    if message_type != "text":
        _safe_reply(whatsapp_client, from_phone, _UNSUPPORTED_MESSAGE)
        return

    text = message.get("text", {}).get("body", "").strip()
    if not text:
        return

    try:
        agent = AgentSession()
        reply = agent.handle_message(db, user, text)
        db.commit()
    except Exception:  # noqa: BLE001 — no queremos que un error del agente tumbe el webhook
        db.rollback()
        logger.exception("Error procesando mensaje de WhatsApp de %s", from_phone)
        reply = "Tuve un problema procesando tu mensaje. Intenta de nuevo en unos minutos."

    _safe_reply(whatsapp_client, from_phone, reply)


def _safe_reply(whatsapp_client: WhatsAppClient, to_phone: str, body: str) -> None:
    try:
        whatsapp_client.send_text(to_phone, body)
    except Exception:  # noqa: BLE001
        logger.exception("No se pudo enviar respuesta de WhatsApp a %s", to_phone)
