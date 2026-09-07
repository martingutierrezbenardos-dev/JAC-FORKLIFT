from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PendingActionStatus(str, PyEnum):
    PENDIENTE = "pendiente"
    CONFIRMADA = "confirmada"
    CANCELADA = "cancelada"
    EXPIRADA = "expirada"


class PendingAction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Acción de nivel 2/3 propuesta por el agente de IA, a la espera de confirmación
    explícita del usuario. Ver docs/architecture.md sección 4.
    """

    __tablename__ = "pending_actions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(80), nullable=False)
    tool_input: Mapped[dict] = mapped_column(JSONB, nullable=False)
    summary_for_user: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[PendingActionStatus] = mapped_column(
        Enum(PendingActionStatus, name="pending_action_status"),
        default=PendingActionStatus.PENDIENTE,
        nullable=False,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
