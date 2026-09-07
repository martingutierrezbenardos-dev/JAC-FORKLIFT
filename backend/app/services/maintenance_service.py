from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import PermissionDeniedError, ValidationDomainError
from app.core.permissions import Permission, has_permission
from app.models.customer import Customer
from app.models.machine import Machine
from app.models.maintenance_record import MaintenanceRecord
from app.models.user import User
from app.schemas.maintenance import MaintenanceCreate, MaintenanceSearchParams
from app.services import audit_service
from app.services.lookup_service import resolve_machine_by_number


def _compute_next_maintenance(
    machine: Machine, data: MaintenanceCreate, fecha_registro: date
) -> tuple[date | None, int | None]:
    proxima_fecha = data.proximo_mantenimiento_fecha
    if proxima_fecha is None and machine.intervalo_dias_mantenimiento:
        proxima_fecha = fecha_registro + timedelta(days=machine.intervalo_dias_mantenimiento)

    proximas_horas = data.proximo_mantenimiento_horas
    if proximas_horas is None and machine.intervalo_horas_mantenimiento:
        horometro_base = data.horometro if data.horometro is not None else machine.horometro
        if horometro_base is not None:
            proximas_horas = horometro_base + machine.intervalo_horas_mantenimiento

    return proxima_fecha, proximas_horas


def create_maintenance_record(
    db: Session, *, actor: User, data: MaintenanceCreate, canal: str = "whatsapp"
) -> MaintenanceRecord:
    if not has_permission(actor.rol, Permission.MAINTENANCE_CREATE):
        raise PermissionDeniedError("No tienes permiso para registrar mantenimientos.")

    machine = resolve_machine_by_number(db, data.maquina_numero)
    if machine is None:
        raise ValidationDomainError(f"No encontré ninguna máquina con número '{data.maquina_numero}'.")

    fecha_registro = date.today()
    proxima_fecha, proximas_horas = _compute_next_maintenance(machine, data, fecha_registro)

    record = MaintenanceRecord(
        maquina_id=machine.id,
        tecnico_id=actor.id,
        fecha=fecha_registro,
        tipo=data.tipo,
        horometro=data.horometro,
        trabajos_realizados=data.trabajos_realizados,
        repuestos_utilizados=data.repuestos_utilizados,
        observaciones=data.observaciones,
        proximo_mantenimiento_fecha=proxima_fecha,
        proximo_mantenimiento_horas=proximas_horas,
    )
    db.add(record)

    machine.fecha_ultimo_mantenimiento = fecha_registro
    machine.fecha_proximo_mantenimiento = proxima_fecha
    machine.horas_proximo_mantenimiento = proximas_horas
    if data.horometro is not None:
        machine.horometro = data.horometro

    db.flush()

    audit_service.record(
        db, usuario_id=actor.id, accion="create", entidad="maintenance_records", entidad_id=record.id,
        datos_nuevos={"maquina": machine.numero_interno, "tipo": record.tipo.value}, canal=canal,
    )
    return record


def search_maintenance_records(
    db: Session, *, actor: User, params: MaintenanceSearchParams
) -> list[MaintenanceRecord]:
    if not has_permission(actor.rol, Permission.MAINTENANCE_READ):
        raise PermissionDeniedError("No tienes permiso para ver el historial de mantenimiento.")

    stmt = select(MaintenanceRecord)
    if params.maquina_numero:
        machine = resolve_machine_by_number(db, params.maquina_numero)
        stmt = stmt.where(MaintenanceRecord.maquina_id == (machine.id if machine else uuid.uuid4()))

    stmt = stmt.order_by(MaintenanceRecord.fecha.desc())
    return list(db.execute(stmt).scalars().all())


def get_pending_maintenance_alerts(db: Session, *, actor: User, dias_anticipacion: int = 7) -> list[dict]:
    if not has_permission(actor.rol, Permission.MAINTENANCE_READ):
        raise PermissionDeniedError("No tienes permiso para ver alertas de mantenimiento.")

    hoy = date.today()
    limite_fecha = hoy + timedelta(days=dias_anticipacion)

    stmt = select(Machine).where(
        or_(
            Machine.fecha_proximo_mantenimiento.isnot(None) & (Machine.fecha_proximo_mantenimiento <= limite_fecha),
            Machine.horas_proximo_mantenimiento.isnot(None)
            & Machine.horometro.isnot(None)
            & (Machine.horometro >= Machine.horas_proximo_mantenimiento),
        )
    )
    machines = list(db.execute(stmt).scalars().all())

    alertas = []
    for m in machines:
        cliente_nombre = None
        if m.cliente_id:
            cliente = db.get(Customer, m.cliente_id)
            cliente_nombre = cliente.nombre if cliente else None

        dias_restantes = (m.fecha_proximo_mantenimiento - hoy).days if m.fecha_proximo_mantenimiento else None
        horas_excedidas = None
        if m.horas_proximo_mantenimiento is not None and m.horometro is not None:
            horas_excedidas = m.horometro - m.horas_proximo_mantenimiento

        alertas.append(
            {
                "numero_interno": m.numero_interno,
                "marca": m.marca,
                "modelo": m.modelo,
                "cliente": cliente_nombre,
                "fecha_proximo_mantenimiento": m.fecha_proximo_mantenimiento,
                "dias_restantes": dias_restantes,
                "horometro_actual": m.horometro,
                "horas_proximo_mantenimiento": m.horas_proximo_mantenimiento,
                "horas_excedidas": horas_excedidas if horas_excedidas is not None and horas_excedidas >= 0 else None,
            }
        )

    return alertas
