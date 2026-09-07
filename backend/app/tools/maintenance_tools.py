from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.maintenance_record import MaintenanceRecord
from app.models.user import User
from app.schemas.maintenance import MaintenanceAlertParams, MaintenanceCreate, MaintenanceSearchParams
from app.services import maintenance_service
from app.tools.serialization import to_jsonable


def _serialize_record(record: MaintenanceRecord) -> dict:
    return {
        "fecha": to_jsonable(record.fecha),
        "tipo": to_jsonable(record.tipo),
        "horometro": record.horometro,
        "trabajos_realizados": record.trabajos_realizados,
        "repuestos_utilizados": record.repuestos_utilizados,
        "observaciones": record.observaciones,
        "proximo_mantenimiento_fecha": to_jsonable(record.proximo_mantenimiento_fecha),
        "proximo_mantenimiento_horas": record.proximo_mantenimiento_horas,
    }


def crear_mantenimiento(db: Session, actor: User, data: MaintenanceCreate) -> dict:
    record = maintenance_service.create_maintenance_record(db, actor=actor, data=data, canal="whatsapp")
    return {"mantenimiento": _serialize_record(record)}


def buscar_mantenimientos(db: Session, actor: User, data: MaintenanceSearchParams) -> dict:
    records = maintenance_service.search_maintenance_records(db, actor=actor, params=data)
    return {"cantidad": len(records), "mantenimientos": [_serialize_record(r) for r in records]}


def buscar_mantenimiento_pendiente(db: Session, actor: User, data: MaintenanceAlertParams) -> dict:
    alertas = maintenance_service.get_pending_maintenance_alerts(
        db, actor=actor, dias_anticipacion=data.dias_anticipacion
    )
    return {"cantidad": len(alertas), "alertas": to_jsonable(alertas)}
