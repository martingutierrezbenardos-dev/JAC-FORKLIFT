from __future__ import annotations

import uuid
from datetime import date as date_type

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, PermissionDeniedError, ValidationDomainError
from app.core.permissions import Permission, has_permission
from app.models.service_order import ServiceOrder, ServiceOrderStatus
from app.models.user import User
from app.schemas.service_order import ServiceOrderCreate, ServiceOrderSearchParams, ServiceOrderUpdate
from app.services import audit_service, user_service
from app.services.lookup_service import resolve_customer_by_name, resolve_machine_by_number

_OPEN_STATUSES = {
    ServiceOrderStatus.PENDIENTE,
    ServiceOrderStatus.ASIGNADO,
    ServiceOrderStatus.EN_RUTA,
    ServiceOrderStatus.EN_SERVICIO,
}


def _next_numero(db: Session) -> str:
    numero = db.execute(text("SELECT nextval('service_order_number_seq')")).scalar_one()
    return f"OT-{numero:06d}"


def create_service_order(
    db: Session, *, actor: User, data: ServiceOrderCreate, canal: str = "whatsapp"
) -> ServiceOrder:
    if not has_permission(actor.rol, Permission.SERVICES_CREATE_OWN):
        raise PermissionDeniedError("No tienes permiso para registrar servicios técnicos.")

    customer = resolve_customer_by_name(db, data.cliente_nombre)
    if data.cliente_nombre and customer is None:
        raise ValidationDomainError(f"No encontré ningún cliente llamado '{data.cliente_nombre}'.")

    machine = resolve_machine_by_number(db, data.maquina_numero)
    if data.maquina_numero and machine is None:
        raise ValidationDomainError(f"No encontré ninguna máquina con número '{data.maquina_numero}'.")

    order = ServiceOrder(
        numero=_next_numero(db),
        cliente_id=customer.id if customer else None,
        maquina_id=machine.id if machine else None,
        tecnico_id=actor.id,
        fecha=date_type.today(),
        motivo=data.motivo,
        estado=ServiceOrderStatus.ASIGNADO,
    )
    db.add(order)
    db.flush()

    audit_service.record(
        db, usuario_id=actor.id, accion="create", entidad="service_orders", entidad_id=order.id,
        datos_nuevos={"numero": order.numero}, canal=canal,
    )
    return order


def _find_target_order(db: Session, actor: User, servicio_numero: str | None) -> ServiceOrder:
    if servicio_numero:
        stmt = select(ServiceOrder).where(
            ServiceOrder.numero == servicio_numero, ServiceOrder.deleted_at.is_(None)
        )
        order = db.execute(stmt).scalars().first()
        if order is None:
            raise NotFoundError(f"No encontré ninguna orden de servicio '{servicio_numero}'.")
        return order

    stmt = (
        select(ServiceOrder)
        .where(ServiceOrder.tecnico_id == actor.id, ServiceOrder.deleted_at.is_(None))
        .where(ServiceOrder.estado.in_(_OPEN_STATUSES))
        .order_by(ServiceOrder.created_at.desc())
    )
    order = db.execute(stmt).scalars().first()
    if order is None:
        raise ValidationDomainError(
            "No tienes ninguna orden de servicio abierta en este momento. Registra una primero."
        )
    return order


def get_service_order(db: Session, order_id: uuid.UUID) -> ServiceOrder:
    order = db.get(ServiceOrder, order_id)
    if order is None or order.deleted_at is not None:
        raise NotFoundError("Orden de servicio no encontrada.")
    return order


def update_service_order(
    db: Session, *, actor: User, data: ServiceOrderUpdate, canal: str = "whatsapp"
) -> ServiceOrder:
    order = _find_target_order(db, actor, data.servicio_numero)

    is_own = order.tecnico_id == actor.id
    if is_own and not has_permission(actor.rol, Permission.SERVICES_UPDATE_OWN):
        raise PermissionDeniedError("No tienes permiso para modificar servicios técnicos.")
    if not is_own and not has_permission(actor.rol, Permission.SERVICES_UPDATE_ALL):
        raise PermissionDeniedError("No puedes modificar la orden de servicio de otro técnico.")

    if data.estado == ServiceOrderStatus.CERRADO and not has_permission(actor.rol, Permission.SERVICES_CLOSE):
        raise PermissionDeniedError("No tienes permiso para cerrar una orden de servicio.")

    if data.cliente_nombre:
        customer = resolve_customer_by_name(db, data.cliente_nombre)
        if customer is None:
            raise ValidationDomainError(f"No encontré ningún cliente llamado '{data.cliente_nombre}'.")
        order.cliente_id = customer.id

    if data.maquina_numero:
        machine = resolve_machine_by_number(db, data.maquina_numero)
        if machine is None:
            raise ValidationDomainError(f"No encontré ninguna máquina con número '{data.maquina_numero}'.")
        order.maquina_id = machine.id

    update_fields = data.model_dump(
        exclude={"servicio_numero", "cliente_nombre", "maquina_numero"}, exclude_unset=True
    )
    for field, value in update_fields.items():
        setattr(order, field, value)
    db.flush()

    audit_service.record(
        db, usuario_id=actor.id, accion="update", entidad="service_orders", entidad_id=order.id,
        datos_nuevos=data.model_dump(
            exclude={"servicio_numero", "cliente_nombre", "maquina_numero"}, exclude_unset=True, mode="json"
        ),
        canal=canal,
    )
    return order


def search_service_orders(db: Session, *, actor: User, params: ServiceOrderSearchParams) -> list[ServiceOrder]:
    stmt = select(ServiceOrder).where(ServiceOrder.deleted_at.is_(None))

    target_tecnico_id: uuid.UUID | None = actor.id
    if params.tecnico_telefono:
        if not has_permission(actor.rol, Permission.SERVICES_READ_ALL):
            target_tecnico_id = actor.id
        else:
            other = user_service.get_by_phone(db, params.tecnico_telefono)
            target_tecnico_id = other.id if other else uuid.uuid4()
    elif not has_permission(actor.rol, Permission.SERVICES_READ_ALL):
        target_tecnico_id = actor.id
    else:
        target_tecnico_id = None

    if target_tecnico_id is not None:
        stmt = stmt.where(ServiceOrder.tecnico_id == target_tecnico_id)
    if params.estado:
        stmt = stmt.where(ServiceOrder.estado == params.estado)
    if params.cliente_nombre:
        customer = resolve_customer_by_name(db, params.cliente_nombre)
        stmt = stmt.where(ServiceOrder.cliente_id == (customer.id if customer else uuid.uuid4()))

    stmt = stmt.order_by(ServiceOrder.created_at.desc())
    return list(db.execute(stmt).scalars().all())
