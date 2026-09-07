from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.vehicle import Vehicle


def search_by_plate(db: Session, patente: str, limit: int = 5) -> list[Vehicle]:
    stmt = select(Vehicle).where(Vehicle.patente.ilike(f"%{patente}%")).limit(limit)
    return list(db.execute(stmt).scalars().all())


def list_all(db: Session) -> list[Vehicle]:
    stmt = select(Vehicle).order_by(Vehicle.patente)
    return list(db.execute(stmt).scalars().all())
