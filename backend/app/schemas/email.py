from __future__ import annotations

from pydantic import BaseModel, Field


class PrepararCorreoInput(BaseModel):
    asunto: str = Field(min_length=2)
    cuerpo: str = Field(min_length=1)
    destinatarios_telefonos: list[str] = Field(
        default_factory=list, description="Teléfonos WhatsApp de destinatarios internos."
    )
    destinatarios_email: list[str] = Field(
        default_factory=list, description="Emails directos de destinatarios (internos o externos)."
    )


class EnviarCorreoInput(BaseModel):
    draft_id: str = Field(description="ID del borrador previamente creado con preparar_correo.")


class BuscarCorreosInput(BaseModel):
    query: str = Field(description="Términos de búsqueda (formato de búsqueda de Gmail, ej. 'from:cliente@x.cl').")
    limite: int = Field(default=10, ge=1, le=50)
