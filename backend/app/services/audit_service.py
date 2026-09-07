from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def record(
    db: Session,
    *,
    usuario_id: uuid.UUID | None,
    accion: str,
    entidad: str,
    entidad_id: uuid.UUID | None,
    datos_anteriores: dict[str, Any] | None = None,
    datos_nuevos: dict[str, Any] | None = None,
    canal: str = "system",
    ip: str | None = None,
) -> AuditLog:
    log = AuditLog(
        usuario_id=usuario_id,
        accion=accion,
        entidad=entidad,
        entidad_id=entidad_id,
        datos_anteriores=datos_anteriores,
        datos_nuevos=datos_nuevos,
        canal=canal,
        ip=ip,
    )
    db.add(log)
    db.flush()
    return log
