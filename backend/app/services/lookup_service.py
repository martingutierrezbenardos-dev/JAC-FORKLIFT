"""Búsquedas de catálogo compartidas (clientes, máquinas) usadas por varios servicios.

Centralizado para que ``expense_service`` y ``service_order_service`` resuelvan nombres de
cliente y números de máquina exactamente de la misma forma.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.machine import Machine


def resolve_customer_by_name(db: Session, nombre: str | None) -> Customer | None:
    if not nombre:
        return None
    stmt = select(Customer).where(Customer.nombre.ilike(f"%{nombre}%"))
    return db.execute(stmt).scalars().first()


def resolve_machine_by_number(db: Session, numero_interno: str | None) -> Machine | None:
    if not numero_interno:
        return None
    stmt = select(Machine).where(Machine.numero_interno.ilike(numero_interno))
    return db.execute(stmt).scalars().first()
