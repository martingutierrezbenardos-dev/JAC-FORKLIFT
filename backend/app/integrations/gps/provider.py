"""Interfaz abstracta de proveedor GPS (sección 15 del brief).

NO se implementa ningún proveedor concreto todavía porque no se conoce cuál usa la empresa.
Esta interfaz existe para que, cuando se defina el proveedor (ej. Wialon, Osmos, Geotab, uno
propio del fabricante de las camionetas), su implementación concreta solo tenga que heredar
de ``GpsProvider`` sin tocar el resto del sistema (tools de IA, servicios, API).

No crear un mock que devuelva datos falsos como si fueran reales: mientras no haya proveedor,
las tools que dependan de esto deben responder explícitamente "GPS aún no está configurado".
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class VehicleLocation:
    vehicle_id: str
    latitude: float
    longitude: float
    recorded_at: datetime
    speed_kmh: float | None = None


@dataclass
class Trip:
    vehicle_id: str
    started_at: datetime
    ended_at: datetime
    origin: str | None
    destination: str | None
    distance_km: float


class GpsProvider(ABC):
    """Contrato que debe implementar cualquier proveedor GPS real."""

    @abstractmethod
    def get_vehicle_location(self, vehicle_id: str) -> VehicleLocation:
        """Ubicación actual de un vehículo."""

    @abstractmethod
    def get_vehicle_history(self, vehicle_id: str, since: datetime, until: datetime) -> list[VehicleLocation]:
        """Historial de posiciones en un rango de tiempo."""

    @abstractmethod
    def get_mileage(self, vehicle_id: str, since: datetime, until: datetime) -> float:
        """Kilómetros recorridos en un rango de tiempo."""

    @abstractmethod
    def get_trips(self, vehicle_id: str, since: datetime, until: datetime) -> list[Trip]:
        """Viajes registrados en un rango de tiempo."""


class GpsNotConfiguredError(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "El proveedor de GPS aún no está configurado. Esta funcionalidad está "
            "planificada para la Fase 4 (ver docs/architecture.md)."
        )
