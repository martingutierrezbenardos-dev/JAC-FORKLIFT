from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import PermissionDeniedError, ValidationDomainError
from app.core.permissions import Permission, has_permission
from app.models.crane import CraneContract, CraneContractStatus, CraneUsage
from app.models.customer import Customer
from app.models.user import User
from app.schemas.crane import CraneContractCreate
from app.services import audit_service
from app.services.lookup_service import resolve_customer_by_name

_ALERT_THRESHOLD = Decimal("0.85")


def _horas_usadas(db: Session, contrato_id: uuid.UUID) -> Decimal:
    total = db.execute(
        select(func.coalesce(func.sum(CraneUsage.horas_usadas), 0)).where(CraneUsage.contrato_id == contrato_id)
    ).scalar_one()
    return Decimal(total)


def _serialize_contract(db: Session, contract: CraneContract) -> dict:
    cliente = db.get(Customer, contract.cliente_id)
    usadas = _horas_usadas(db, contract.id)
    disponibles = contract.horas_contratadas - usadas
    porcentaje = float(usadas / contract.horas_contratadas) if contract.horas_contratadas else 0.0
    return {
        "id": str(contract.id),
        "cliente": cliente.nombre if cliente else None,
        "periodo_inicio": contract.periodo_inicio.isoformat(),
        "periodo_fin": contract.periodo_fin.isoformat(),
        "horas_contratadas": float(contract.horas_contratadas),
        "horas_utilizadas": float(usadas),
        "horas_disponibles": float(disponibles),
        "porcentaje_usado": round(porcentaje * 100, 1),
        "alerta": porcentaje >= float(_ALERT_THRESHOLD),
        "estado": contract.estado.value,
    }


def _active_contracts_for_customer(db: Session, cliente_id: uuid.UUID) -> list[CraneContract]:
    stmt = (
        select(CraneContract)
        .where(CraneContract.cliente_id == cliente_id, CraneContract.estado == CraneContractStatus.ACTIVO)
        .order_by(CraneContract.periodo_inicio.desc())
    )
    return list(db.execute(stmt).scalars().all())


def create_crane_contract(db: Session, *, actor: User, data: CraneContractCreate, canal: str = "web") -> dict:
    if not has_permission(actor.rol, Permission.CRANES_MANAGE):
        raise PermissionDeniedError("No tienes permiso para crear contratos de grúa.")

    customer = resolve_customer_by_name(db, data.cliente_nombre)
    if customer is None:
        raise ValidationDomainError(f"No encontré ningún cliente llamado '{data.cliente_nombre}'.")

    contract = CraneContract(
        cliente_id=customer.id,
        periodo_inicio=data.periodo_inicio,
        periodo_fin=data.periodo_fin,
        horas_contratadas=data.horas_contratadas,
        costo_hora=data.costo_hora,
        moneda=data.moneda,
        observaciones=data.observaciones,
    )
    db.add(contract)
    db.flush()

    audit_service.record(
        db, usuario_id=actor.id, accion="create", entidad="crane_contracts", entidad_id=contract.id,
        datos_nuevos={"cliente": customer.nombre, "horas_contratadas": str(data.horas_contratadas)}, canal=canal,
    )
    return _serialize_contract(db, contract)


def list_active_contracts(db: Session) -> list[dict]:
    stmt = select(CraneContract).where(CraneContract.estado == CraneContractStatus.ACTIVO)
    contracts = list(db.execute(stmt).scalars().all())
    return [_serialize_contract(db, c) for c in contracts]


def registrar_uso_grua(
    db: Session,
    *,
    actor: User,
    cliente_nombre: str,
    horas_usadas: Decimal,
    fecha: date | None = None,
    observaciones: str | None = None,
    canal: str = "whatsapp",
) -> dict:
    if not has_permission(actor.rol, Permission.CRANES_REGISTER):
        raise PermissionDeniedError("No tienes permiso para registrar uso de grúa.")

    customer = resolve_customer_by_name(db, cliente_nombre)
    if customer is None:
        raise ValidationDomainError(f"No encontré ningún cliente llamado '{cliente_nombre}'.")

    contracts = _active_contracts_for_customer(db, customer.id)
    if not contracts:
        raise ValidationDomainError(f"No encontré un contrato de grúa activo para '{cliente_nombre}'.")
    contract = contracts[0]

    usage = CraneUsage(
        contrato_id=contract.id,
        registrado_por=actor.id,
        fecha=fecha or date.today(),
        horas_usadas=horas_usadas,
        observaciones=observaciones,
    )
    db.add(usage)
    db.flush()

    audit_service.record(
        db, usuario_id=actor.id, accion="create", entidad="crane_usage", entidad_id=usage.id,
        datos_nuevos={"contrato_id": str(contract.id), "horas_usadas": str(horas_usadas)}, canal=canal,
    )
    return {"contrato": _serialize_contract(db, contract)}


def consultar_horas_grua(db: Session, *, actor: User, cliente_nombre: str | None = None) -> dict:
    if cliente_nombre:
        if not has_permission(actor.rol, Permission.CRANES_READ):
            raise PermissionDeniedError("No tienes permiso para consultar contratos de grúa.")
        customer = resolve_customer_by_name(db, cliente_nombre)
        if customer is None:
            raise ValidationDomainError(f"No encontré ningún cliente llamado '{cliente_nombre}'.")
        contracts = _active_contracts_for_customer(db, customer.id)
        if not contracts:
            raise ValidationDomainError(f"No encontré un contrato de grúa activo para '{cliente_nombre}'.")
    else:
        if not has_permission(actor.rol, Permission.CRANES_MANAGE):
            raise PermissionDeniedError(
                "Indica el cliente para consultar su contrato, o pide este reporte a administración/gerencia."
            )
        stmt = select(CraneContract).where(CraneContract.estado == CraneContractStatus.ACTIVO)
        contracts = list(db.execute(stmt).scalars().all())

    return {"contratos": [_serialize_contract(db, c) for c in contracts]}


def get_contracts_near_limit(db: Session, *, threshold: Decimal = _ALERT_THRESHOLD) -> list[dict]:
    stmt = select(CraneContract).where(CraneContract.estado == CraneContractStatus.ACTIVO)
    contracts = list(db.execute(stmt).scalars().all())
    serialized = [_serialize_contract(db, c) for c in contracts]
    return [c for c in serialized if c["porcentaje_usado"] >= float(threshold) * 100]
