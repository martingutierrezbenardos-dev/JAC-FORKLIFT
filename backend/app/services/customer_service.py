from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.customer import Customer


def search_by_name(db: Session, nombre: str, limit: int = 5) -> list[Customer]:
    stmt = select(Customer).where(Customer.nombre.ilike(f"%{nombre}%")).limit(limit)
    return list(db.execute(stmt).scalars().all())


def list_all(db: Session) -> list[Customer]:
    stmt = select(Customer).order_by(Customer.nombre)
    return list(db.execute(stmt).scalars().all())
