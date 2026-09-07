import pytest

from app.core.errors import PermissionDeniedError, ValidationDomainError
from app.core.permissions import UserRole
from app.models.customer import Customer
from app.models.machine import Machine
from app.models.service_order import ServiceOrderStatus
from app.schemas.service_order import ServiceOrderCreate, ServiceOrderSearchParams, ServiceOrderUpdate
from app.services import service_order_service
from tests.conftest import make_user


def test_crear_servicio_genera_numero_y_queda_asignado(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56966666601")

    orden = service_order_service.create_service_order(
        db_session, actor=tecnico, data=ServiceOrderCreate(motivo="Revisar máquina 33")
    )

    assert orden.numero.startswith("OT-")
    assert orden.tecnico_id == tecnico.id
    assert orden.estado == ServiceOrderStatus.ASIGNADO


def test_crear_servicio_resuelve_cliente_y_maquina(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56966666602")
    cliente = Customer(nombre="Cliente ABC")
    maquina = Machine(numero_interno="33", estado="operativa")
    db_session.add_all([cliente, maquina])
    db_session.flush()

    orden = service_order_service.create_service_order(
        db_session, actor=tecnico,
        data=ServiceOrderCreate(motivo="Cambio de alternador", cliente_nombre="Cliente ABC", maquina_numero="33"),
    )

    assert orden.cliente_id == cliente.id
    assert orden.maquina_id == maquina.id


def test_crear_servicio_cliente_inexistente_falla(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56966666603")

    with pytest.raises(ValidationDomainError):
        service_order_service.create_service_order(
            db_session, actor=tecnico,
            data=ServiceOrderCreate(motivo="Visita", cliente_nombre="Cliente que no existe"),
        )


def test_actualizar_servicio_usa_la_orden_abierta_mas_reciente_sin_pedir_numero(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56966666604")
    orden = service_order_service.create_service_order(
        db_session, actor=tecnico, data=ServiceOrderCreate(motivo="Visita a cliente")
    )

    actualizada = service_order_service.update_service_order(
        db_session, actor=tecnico,
        data=ServiceOrderUpdate(diagnostico="Alternador dañado", trabajo_realizado="Se reemplazó el alternador"),
    )

    assert actualizada.id == orden.id
    assert actualizada.diagnostico == "Alternador dañado"


def test_actualizar_servicio_sin_orden_abierta_falla(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56966666605")

    with pytest.raises(ValidationDomainError):
        service_order_service.update_service_order(
            db_session, actor=tecnico, data=ServiceOrderUpdate(diagnostico="algo")
        )


def test_tecnico_no_puede_modificar_servicio_de_otro(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56966666606")
    otro = make_user(db_session, rol=UserRole.TECNICO, telefono="+56966666607", nombre="Otro")
    orden = service_order_service.create_service_order(
        db_session, actor=otro, data=ServiceOrderCreate(motivo="Visita")
    )

    with pytest.raises(PermissionDeniedError):
        service_order_service.update_service_order(
            db_session, actor=tecnico, data=ServiceOrderUpdate(servicio_numero=orden.numero, diagnostico="x")
        )


def test_administracion_no_puede_cerrar_orden_de_servicio(db_session):
    admin = make_user(db_session, rol=UserRole.ADMINISTRACION, telefono="+56966666608")
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56966666609", nombre="Tecnico")
    orden = service_order_service.create_service_order(
        db_session, actor=tecnico, data=ServiceOrderCreate(motivo="Visita")
    )

    with pytest.raises(PermissionDeniedError):
        service_order_service.update_service_order(
            db_session, actor=admin,
            data=ServiceOrderUpdate(servicio_numero=orden.numero, estado=ServiceOrderStatus.CERRADO),
        )


def test_jefe_servicios_tecnicos_puede_cerrar_orden(db_session):
    jefe = make_user(db_session, rol=UserRole.JEFE_SERVICIOS_TECNICOS, telefono="+56966666610")
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56966666611", nombre="Tecnico2")
    orden = service_order_service.create_service_order(
        db_session, actor=tecnico, data=ServiceOrderCreate(motivo="Visita")
    )

    cerrada = service_order_service.update_service_order(
        db_session, actor=jefe,
        data=ServiceOrderUpdate(servicio_numero=orden.numero, estado=ServiceOrderStatus.CERRADO),
    )

    assert cerrada.estado == ServiceOrderStatus.CERRADO


def test_tecnico_solo_ve_sus_propias_ordenes(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56966666612")
    otro = make_user(db_session, rol=UserRole.TECNICO, telefono="+56966666613", nombre="Otro3")
    service_order_service.create_service_order(db_session, actor=otro, data=ServiceOrderCreate(motivo="Visita otro"))

    resultados = service_order_service.search_service_orders(
        db_session, actor=tecnico, params=ServiceOrderSearchParams()
    )

    assert resultados == []
