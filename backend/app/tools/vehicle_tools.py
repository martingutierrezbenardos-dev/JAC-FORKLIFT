from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.vehicle import BuscarVehiculoInput, ConsultarRangoVehiculoInput, ConsultarUbicacionVehiculoInput
from app.services import gps_service, vehicle_service


def buscar_vehiculo(db: Session, actor: User, data: BuscarVehiculoInput) -> dict:
    vehiculos = vehicle_service.search_by_plate(db, data.patente)
    return {
        "resultados": [
            {
                "patente": v.patente,
                "marca": v.marca,
                "modelo": v.modelo,
                "anio": v.anio,
                "sucursal": v.sucursal,
                "estado": v.estado,
                "observaciones": v.observaciones,
            }
            for v in vehiculos
        ]
    }


def consultar_ubicacion_vehiculo(db: Session, actor: User, data: ConsultarUbicacionVehiculoInput) -> dict:
    return gps_service.consultar_ubicacion(db, actor=actor, patente=data.patente)


def consultar_kilometraje_vehiculo(db: Session, actor: User, data: ConsultarRangoVehiculoInput) -> dict:
    return gps_service.consultar_kilometraje(db, actor=actor, patente=data.patente, desde=data.desde, hasta=data.hasta)


def consultar_viajes_vehiculo(db: Session, actor: User, data: ConsultarRangoVehiculoInput) -> dict:
    return gps_service.consultar_viajes(db, actor=actor, patente=data.patente, desde=data.desde, hasta=data.hasta)
