from __future__ import annotations

import uuid
from enum import Enum as PyEnum

from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MessageRole(str, PyEnum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ConversationMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Historial corto de conversación por usuario, usado para dar contexto al LLM.

    La memoria del sistema vive en la base de datos, no en el modelo (principio del brief).
    """

    __tablename__ = "conversation_messages"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole, name="message_role"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
