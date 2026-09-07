from __future__ import annotations

from pydantic import BaseModel


class InboundWhatsAppMessage(BaseModel):
    """Representación normalizada de un mensaje entrante, extraída del payload de Meta."""

    from_phone: str
    message_type: str  # "text", "audio", "image", "document", etc.
    text: str | None = None
    wa_message_id: str
