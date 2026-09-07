from datetime import date, timedelta

import pytest

from app.core.errors import ValidationDomainError
from app.core.permissions import UserRole
from app.models.machine import Machine
from app.schemas.maintenance import MaintenanceAlertParams, MaintenanceCreate, MaintenanceSearchParams
from app.services import maintenance_service
from tests.conftest import make_user


def test_crear_mantenimiento_calcula_proxima_fecha_desde_intervalo(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56900111001")
    maquina = Machine(numero_interno="M1", estado="operativa", intervalo_dias_mantenimiento=90)
    db_session.add(maquina)
    db_session.flush()

    record = maintenance_service.create_maintenance_record(
        db_session, actor=tecnico,
        data=MaintenanceCreate(maquina_numero="M1", trabajos_realizados="Cambio de aceite"),
    )

    hoy = date.today()
    assert record.fecha == hoy
    assert record.proximo_mantenimiento_fecha == hoy + timedelta(days=90)
    assert maquina.fecha_ultimo_mantenimiento == hoy
    assert maquina.fecha_proximo_mantenimiento == hoy + timedelta(days=90)


def test_crear_mantenimiento_calcula_proximas_horas_desde_intervalo(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56900111002")
    maquina = Machine(numero_interno="M2", estado="operativa", intervalo_horas_mantenimiento=500, horometro=1000)
    db_session.add(maquina)
    db_session.flush()

    record = maintenance_service.create_maintenance_record(
        db_session, actor=tecnico,
        data=MaintenanceCreate(maquina_numero="M2", trabajos_realizados="Revisión", horometro=1000),
    )

    assert record.proximo_mantenimiento_horas == 1500
    assert maquina.horas_proximo_mantenimiento == 1500
    assert maquina.horometro == 1000


def test_crear_mantenimiento_respeta_valores_explicitos(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56900111003")
    maquina = Machine(numero_interno="M3", estado="operativa", intervalo_dias_mantenimiento=90)
    db_session.add(maquina)
    db_session.flush()

    fecha_manual = date.today() + timedelta(days=30)
    record = maintenance_service.create_maintenance_record(
        db_session, actor=tecnico,
        data=MaintenanceCreate(
            maquina_numero="M3", trabajos_realizados="Cambio de rodamientos",
            proximo_mantenimiento_fecha=fecha_manual,
        ),
    )

    assert record.proximo_mantenimiento_fecha == fecha_manual


def test_crear_mantenimiento_maquina_inexistente_falla(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56900111004")

    with pytest.raises(ValidationDomainError):
        maintenance_service.create_maintenance_record(
            db_session, actor=tecnico,
            data=MaintenanceCreate(maquina_numero="NOEXISTE", trabajos_realizados="Algo"),
        )


def test_buscar_mantenimiento_pendiente_detecta_atraso_por_fecha_y_horas(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56900111005")
    hoy = date.today()

    atrasada_fecha = Machine(
        numero_interno="A1", estado="operativa",
        fecha_proximo_mantenimiento=hoy - timedelta(days=5),
    )
    atrasada_horas = Machine(
        numero_interno="A2", estado="operativa", horometro=600, horas_proximo_mantenimiento=500,
    )
    al_dia = Machine(numero_interno="A3", estado="operativa")
    db_session.add_all([atrasada_fecha, atrasada_horas, al_dia])
    db_session.flush()

    alertas = maintenance_service.get_pending_maintenance_alerts(db_session, actor=tecnico, dias_anticipacion=7)
    numeros = {a["numero_interno"] for a in alertas}

    assert "A1" in numeros
    assert "A2" in numeros
    assert "A3" not in numeros


def test_buscar_mantenimientos_filtra_por_maquina(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56900111006")
    m1 = Machine(numero_interno="F1", estado="operativa")
    m2 = Machine(numero_interno="F2", estado="operativa")
    db_session.add_all([m1, m2])
    db_session.flush()

    maintenance_service.create_maintenance_record(
        db_session, actor=tecnico, data=MaintenanceCreate(maquina_numero="F1", trabajos_realizados="Trabajo 1")
    )
    maintenance_service.create_maintenance_record(
        db_session, actor=tecnico, data=MaintenanceCreate(maquina_numero="F2", trabajos_realizados="Trabajo 2")
    )

    resultados = maintenance_service.search_maintenance_records(
        db_session, actor=tecnico, params=MaintenanceSearchParams(maquina_numero="F1")
    )

    assert len(resultados) == 1
    assert resultados[0].trabajos_realizados == "Trabajo 1"
