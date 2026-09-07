from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import BuscarUsuarioInput
from app.services import user_service
from app.tools.serialization import to_jsonable


def buscar_usuario(db: Session, actor: User, data: BuscarUsuarioInput) -> dict:
    if data.telefono:
        found = user_service.get_by_phone(db, data.telefono)
        resultados = [found] if found else []
    elif data.nombre:
        resultados = user_service.search_by_name(db, data.nombre)
    else:
        resultados = []

    return {
        "resultados": [
            {
                "nombre_completo": u.nombre_completo,
                "telefono_whatsapp": u.telefono_whatsapp,
                "cargo": u.cargo,
                "rol": to_jsonable(u.rol),
                "sucursal": u.sucursal,
            }
            for u in resultados
        ]
    }
