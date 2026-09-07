"""Extracción de datos de comprobantes (boletas/facturas) a partir de una foto, usando la
capacidad de visión de Claude (sección 5 del brief: OCR de comprobantes).

Es una integración REAL (la Messages API de Anthropic acepta imágenes), no un mock. Se le
pide explícitamente al modelo que NO invente datos que no aparezcan en la imagen — todo campo
no visible queda en null. El resultado es solo una sugerencia para que el agente
conversacional complete el registro de un gasto (ver app/api/routes/whatsapp.py); esta
función nunca escribe en la base de datos por sí misma.
"""
from __future__ import annotations

import base64
import json

from pydantic import BaseModel, ValidationError

from app.core.config import get_settings

_SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}

_EXTRACTION_PROMPT = """\
Analiza esta imagen de un comprobante o boleta chilena. Extrae ÚNICAMENTE los datos que \
aparecen literalmente en la imagen. Si un dato no está visible o no puedes leerlo con \
certeza, usa null para ese campo — NUNCA inventes ni asumas un valor.

Responde EXCLUSIVAMENTE con un JSON con esta forma exacta (sin texto adicional, sin \
markdown ni explicaciones):
{"proveedor": string|null, "fecha": "YYYY-MM-DD"|null, "monto": number|null, \
"moneda": "CLP"|"USD"|null, "numero_documento": string|null, "productos": string[], \
"impuestos": number|null, "nota": string|null}

"nota" es para una observación breve si algo no quedó claro (ej. "monto poco legible").
"""


class ExtractedReceipt(BaseModel):
    proveedor: str | None = None
    fecha: str | None = None
    monto: float | None = None
    moneda: str | None = None
    numero_documento: str | None = None
    productos: list[str] = []
    impuestos: float | None = None
    nota: str | None = None


class ReceiptExtractionNotConfiguredError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("ANTHROPIC_API_KEY no está configurado; no se puede leer el comprobante.")


class UnsupportedImageTypeError(RuntimeError):
    def __init__(self, mime_type: str) -> None:
        super().__init__(f"Tipo de imagen no soportado para extracción: {mime_type}")


def extract_receipt_data(image_bytes: bytes, mime_type: str, *, client=None) -> ExtractedReceipt:
    """``client`` es inyectable solo para tests (un doble con la misma interfaz que
    ``anthropic.Anthropic``); en producción siempre se construye el cliente real."""
    clean_mime = mime_type.split(";")[0].strip().lower()
    if clean_mime not in _SUPPORTED_IMAGE_TYPES:
        raise UnsupportedImageTypeError(clean_mime)

    if client is None:
        settings = get_settings()
        if not settings.anthropic_api_key:
            raise ReceiptExtractionNotConfiguredError()

        import anthropic  # import diferido: no requerido si no se usa esta función

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        model = settings.anthropic_model
    else:
        model = get_settings().anthropic_model

    image_b64 = base64.b64encode(image_bytes).decode("ascii")

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": clean_mime, "data": image_b64},
                    },
                    {"type": "text", "text": _EXTRACTION_PROMPT},
                ],
            }
        ],
    )

    raw_text = "".join(block.text for block in response.content if block.type == "text")
    try:
        data = json.loads(raw_text)
        return ExtractedReceipt.model_validate(data)
    except (json.JSONDecodeError, ValidationError):
        return ExtractedReceipt(nota="No se pudo interpretar la respuesta de extracción del comprobante.")
