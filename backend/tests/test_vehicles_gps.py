from datetime import datetime, timezone

import pytest

from app.core.errors import ValidationDomainError
from app.core.permissions import UserRole
from app.integrations.gps.provider import GpsNotConfiguredError, Trip, VehicleLocation
from app.models.vehicle import Vehicle
from app.services import gps_service, vehicle_service
from tests.conftest import make_user


class _FakeGpsProvider:
    def get_vehicle_location(self, vehicle_id):
        return VehicleLocation(
            vehicle_id=vehicle_id, latitude=-33.45, longitude=-70.66,
            recorded_at=datetime(2026, 1, 1, tzinfo=timezone.utc), speed_kmh=42.0,
        )

    def get_vehicle_history(self, vehicle_id, since, until):
        return [self.get_vehicle_location(vehicle_id)]

    def get_mileage(self, vehicle_id, since, until):
        return 123.4

    def get_trips(self, vehicle_id, since, until):
        return [
            Trip(
                vehicle_id=vehicle_id, started_at=since, ended_at=until,
                origin="Base", destination="Cliente A", distance_km=50.0,
            )
        ]


def test_buscar_vehiculo(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56900666001")
    db_session.add(Vehicle(patente="ABCD12", marca="Toyota", estado="operativo"))
    db_session.flush()

    resultados = vehicle_service.search_by_plate(db_session, "ABCD")

    assert len(resultados) == 1
    assert resultados[0].patente == "ABCD12"


def test_gps_sin_proveedor_configurado_da_error_claro(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56900666002")
    db_session.add(Vehicle(patente="EFGH34", estado="operativo"))
    db_session.flush()

    with pytest.raises(ValidationDomainError, match="GPS"):
        gps_service.consultar_ubicacion(db_session, actor=tecnico, patente="EFGH34")


def test_gps_vehiculo_inexistente_falla_antes_de_llegar_al_gps(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56900666003")

    with pytest.raises(ValidationDomainError, match="vehículo"):
        gps_service.consultar_ubicacion(db_session, actor=tecnico, patente="NOEXISTE")


def test_gps_con_proveedor_inyectado_devuelve_datos_reales(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56900666004")
    db_session.add(Vehicle(patente="IJKL56", estado="operativo"))
    db_session.flush()

    ubicacion = gps_service.consultar_ubicacion(
        db_session, actor=tecnico, patente="IJKL56", provider_factory=lambda: _FakeGpsProvider()
    )
    assert ubicacion["latitud"] == -33.45

    desde = datetime(2026, 1, 1, tzinfo=timezone.utc)
    hasta = datetime(2026, 1, 31, tzinfo=timezone.utc)
    km = gps_service.consultar_kilometraje(
        db_session, actor=tecnico, patente="IJKL56", desde=desde, hasta=hasta,
        provider_factory=lambda: _FakeGpsProvider(),
    )
    assert km["kilometros"] == 123.4

    viajes = gps_service.consultar_viajes(
        db_session, actor=tecnico, patente="IJKL56", desde=desde, hasta=hasta,
        provider_factory=lambda: _FakeGpsProvider(),
    )
    assert viajes["cantidad"] == 1
    assert viajes["viajes"][0]["destino"] == "Cliente A"


def test_gps_provider_factory_que_lanza_not_configured_se_traduce(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56900666005")
    db_session.add(Vehicle(patente="MNOP78", estado="operativo"))
    db_session.flush()

    def _raise():
        raise GpsNotConfiguredError()

    with pytest.raises(ValidationDomainError):
        gps_service.consultar_ubicacion(db_session, actor=tecnico, patente="MNOP78", provider_factory=_raise)
