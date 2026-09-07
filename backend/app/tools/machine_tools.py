from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.user import User
from app.schemas.machine import BuscarMaquinaInput
from app.services import machine_service
from app.tools.serialization import to_jsonable


def buscar_maquina(db: Session, actor: User, data: BuscarMaquinaInput) -> dict:
    resultados = machine_service.search_by_number(db, data.numero_interno)

    fichas = []
    for m in resultados:
        cliente_nombre = None
        if m.cliente_id:
            cliente = db.get(Customer, m.cliente_id)
            cliente_nombre = cliente.nombre if cliente else None
        fichas.append(
            {
                "numero_interno": m.numero_interno,
                "numero_serie": m.numero_serie,
                "marca": m.marca,
                "modelo": m.modelo,
                "tipo": m.tipo,
                "cliente": cliente_nombre,
                "horometro": m.horometro,
                "estado": m.estado,
                "ubicacion": m.ubicacion,
                "observaciones": m.observaciones,
                "fecha_ultimo_mantenimiento": m.fecha_ultimo_mantenimiento,
                "fecha_proximo_mantenimiento": m.fecha_proximo_mantenimiento,
                "horas_proximo_mantenimiento": m.horas_proximo_mantenimiento,
            }
        )
    return {"resultados": to_jsonable(fichas)}
