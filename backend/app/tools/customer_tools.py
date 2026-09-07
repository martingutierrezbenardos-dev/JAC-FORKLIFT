from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.customer import BuscarClienteInput
from app.services import customer_service


def buscar_cliente(db: Session, actor: User, data: BuscarClienteInput) -> dict:
    resultados = customer_service.search_by_name(db, data.nombre)
    return {
        "resultados": [
            {
                "nombre": c.nombre,
                "rut": c.rut,
                "direccion": c.direccion,
                "comuna": c.comuna,
                "ciudad": c.ciudad,
                "contacto": c.contacto,
                "telefono": c.telefono,
                "email": c.email,
                "tipo_cliente": c.tipo_cliente,
                "estado": c.estado,
            }
            for c in resultados
        ]
    }
