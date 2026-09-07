from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.machine import Machine


def search_by_number(db: Session, numero_interno: str, limit: int = 5) -> list[Machine]:
    stmt = select(Machine).where(Machine.numero_interno.ilike(f"%{numero_interno}%")).limit(limit)
    return list(db.execute(stmt).scalars().all())


def list_all(db: Session) -> list[Machine]:
    stmt = select(Machine).order_by(Machine.numero_interno)
    return list(db.execute(stmt).scalars().all())
