from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.service_order import ServiceOrder
from app.models.user import User
from app.schemas.service_order import ServiceOrderCreate, ServiceOrderSearchParams, ServiceOrderUpdate
from app.services import service_order_service
from app.tools.serialization import to_jsonable


def _serialize_order(order: ServiceOrder) -> dict:
    return {
        "numero": order.numero,
        "fecha": to_jsonable(order.fecha),
        "hora_salida": to_jsonable(order.hora_salida),
        "hora_llegada": to_jsonable(order.hora_llegada),
        "hora_inicio": to_jsonable(order.hora_inicio),
        "hora_termino": to_jsonable(order.hora_termino),
        "motivo": order.motivo,
        "diagnostico": order.diagnostico,
        "trabajo_realizado": order.trabajo_realizado,
        "repuestos_utilizados": order.repuestos_utilizados,
        "estado": to_jsonable(order.estado),
        "observaciones": order.observaciones,
    }


def crear_servicio(db: Session, actor: User, data: ServiceOrderCreate) -> dict:
    order = service_order_service.create_service_order(db, actor=actor, data=data, canal="whatsapp")
    return {"servicio": _serialize_order(order)}


def actualizar_servicio(db: Session, actor: User, data: ServiceOrderUpdate) -> dict:
    order = service_order_service.update_service_order(db, actor=actor, data=data, canal="whatsapp")
    return {"servicio": _serialize_order(order)}


def buscar_servicios(db: Session, actor: User, data: ServiceOrderSearchParams) -> dict:
    orders = service_order_service.search_service_orders(db, actor=actor, params=data)
    return {"cantidad": len(orders), "servicios": [_serialize_order(o) for o in orders]}
