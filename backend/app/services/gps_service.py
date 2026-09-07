"""Capa de servicio para consultas de GPS de vehículos (sección 15 del brief).

Todavía no existe ningún ``GpsProvider`` concreto registrado porque no se conoce qué
proveedor de GPS usa la empresa (Wialon, Geotab, uno del fabricante de las camionetas, etc.).
``_get_gps_provider`` es el ÚNICO lugar que hay que tocar cuando se defina el proveedor:
se reemplaza por la construcción del cliente real (siguiendo el mismo patrón que
``calendar_service``/``email_service``, con un ``provider_factory`` inyectable para tests),
y las tools, permisos y respuestas siguen funcionando igual.

Mientras tanto, cada función aquí traduce ``GpsNotConfiguredError`` en un mensaje claro para
el usuario en vez de simular una ubicación o un kilometraje falso.
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable

from sqlalchemy.orm import Session

from app.core.errors import PermissionDeniedError, ValidationDomainError
from app.core.permissions import Permission, has_permission
from app.integrations.gps.provider import GpsNotConfiguredError, GpsProvider
from app.models.user import User
from app.services import vehicle_service

ProviderFactory = Callable[[], GpsProvider]


def _get_gps_provider() -> GpsProvider:
    raise GpsNotConfiguredError()


def _resolve_vehicle(db: Session, patente: str):
    vehicles = vehicle_service.search_by_plate(db, patente)
    if not vehicles:
        raise ValidationDomainError(f"No encontré ningún vehículo con patente '{patente}'.")
    return vehicles[0]


def _build_provider(provider_factory: ProviderFactory) -> GpsProvider:
    try:
        return provider_factory()
    except GpsNotConfiguredError as exc:
        raise ValidationDomainError(str(exc)) from exc


def consultar_ubicacion(
    db: Session, *, actor: User, patente: str, provider_factory: ProviderFactory = _get_gps_provider
) -> dict:
    if not has_permission(actor.rol, Permission.VEHICLES_READ):
        raise PermissionDeniedError("No tienes permiso para consultar vehículos.")
    vehicle = _resolve_vehicle(db, patente)
    provider = _build_provider(provider_factory)

    location = provider.get_vehicle_location(str(vehicle.id))
    return {
        "patente": vehicle.patente,
        "latitud": location.latitude,
        "longitud": location.longitude,
        "velocidad_kmh": location.speed_kmh,
        "registrado_en": location.recorded_at.isoformat(),
    }


def consultar_kilometraje(
    db: Session,
    *,
    actor: User,
    patente: str,
    desde: datetime,
    hasta: datetime,
    provider_factory: ProviderFactory = _get_gps_provider,
) -> dict:
    if not has_permission(actor.rol, Permission.VEHICLES_READ):
        raise PermissionDeniedError("No tienes permiso para consultar vehículos.")
    vehicle = _resolve_vehicle(db, patente)
    provider = _build_provider(provider_factory)

    kilometros = provider.get_mileage(str(vehicle.id), desde, hasta)
    return {"patente": vehicle.patente, "kilometros": kilometros, "desde": desde.isoformat(), "hasta": hasta.isoformat()}


def consultar_viajes(
    db: Session,
    *,
    actor: User,
    patente: str,
    desde: datetime,
    hasta: datetime,
    provider_factory: ProviderFactory = _get_gps_provider,
) -> dict:
    if not has_permission(actor.rol, Permission.VEHICLES_READ):
        raise PermissionDeniedError("No tienes permiso para consultar vehículos.")
    vehicle = _resolve_vehicle(db, patente)
    provider = _build_provider(provider_factory)

    trips = provider.get_trips(str(vehicle.id), desde, hasta)
    return {
        "patente": vehicle.patente,
        "cantidad": len(trips),
        "viajes": [
            {
                "inicio": t.started_at.isoformat(),
                "fin": t.ended_at.isoformat(),
                "origen": t.origin,
                "destino": t.destination,
                "distancia_km": t.distance_km,
            }
            for t in trips
        ],
    }
