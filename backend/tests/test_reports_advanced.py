from datetime import date, datetime, timedelta, timezone

from app.core.permissions import UserRole
from app.models.customer import Customer
from app.models.expense import PaymentMethod, ReimbursementStatus
from app.models.machine import Machine
from app.models.service_order import ServiceOrderStatus
from app.schemas.expense import ExpenseCreate, ExpenseUpdate
from app.schemas.service_order import ServiceOrderUpdate
from app.services import expense_service, report_service, service_order_service
from tests.conftest import make_user


def test_resolve_periodo_dia_semana_mes():
    hoy = date.today()

    assert report_service.resolve_periodo("dia", None, None) == (hoy, hoy)
    assert report_service.resolve_periodo("semana", None, None) == (hoy - timedelta(days=6), hoy)
    assert report_service.resolve_periodo("mes", None, None) == (hoy.replace(day=1), hoy)


def test_resolve_periodo_no_pisa_fechas_explicitas():
    desde = date(2026, 1, 1)
    hasta = date(2026, 1, 15)
    assert report_service.resolve_periodo("mes", desde, hasta) == (desde, hasta)


def test_reporte_gastos_incluye_desgloses(db_session):
    admin = make_user(db_session, rol=UserRole.ADMINISTRACION, telefono="+56900222001", sucursal="Santiago")
    tecnico = make_user(
        db_session, rol=UserRole.TECNICO, telefono="+56900222002", nombre="Tecnico", sucursal="Antofagasta"
    )
    cliente = Customer(nombre="Cliente Reporte")
    maquina = Machine(numero_interno="R1", estado="operativa")
    db_session.add_all([cliente, maquina])
    db_session.flush()

    expense_service.create_expense(
        db_session, actor=tecnico,
        data=ExpenseCreate(
            fecha=date.today(), monto=10000, categoria="repuesto", proveedor="Proveedor X",
            forma_pago=PaymentMethod.EFECTIVO_PROPIO, cliente_nombre="Cliente Reporte", maquina_numero="R1",
        ),
    )

    reporte = report_service.generar_reporte_gastos(db_session, actor=admin, desde=None, hasta=None)

    assert reporte["total"] == 10000
    assert reporte["por_trabajador"].get("Tecnico User") == 10000
    assert reporte["por_proveedor"].get("Proveedor X") == 10000
    assert reporte["por_cliente"].get("Cliente Reporte") == 10000
    assert reporte["por_maquina"].get("R1") == 10000
    assert reporte["por_sucursal"].get("Antofagasta") == 10000
    assert reporte["pendiente_de_reembolso"] == 10000


def test_reporte_gastos_no_cuenta_reembolso_ya_pagado(db_session):
    admin = make_user(db_session, rol=UserRole.ADMINISTRACION, telefono="+56900222003")
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56900222004", nombre="Tecnico2")

    gasto = expense_service.create_expense(
        db_session, actor=tecnico,
        data=ExpenseCreate(fecha=date.today(), monto=5000, categoria="peaje", forma_pago=PaymentMethod.EFECTIVO_PROPIO),
    )
    expense_service.update_expense(
        db_session, actor=admin, expense_id=gasto.id, data=ExpenseUpdate(estado_reembolso=ReimbursementStatus.PAGADO)
    )

    reporte = report_service.generar_reporte_gastos(db_session, actor=admin, desde=None, hasta=None)

    assert reporte["pendiente_de_reembolso"] == 0.0


def test_reporte_servicios_calcula_tiempos_promedio(db_session):
    jefe = make_user(db_session, rol=UserRole.JEFE_SERVICIOS_TECNICOS, telefono="+56900222005")
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56900222006", nombre="TecnicoServ")

    from app.schemas.service_order import ServiceOrderCreate

    orden = service_order_service.create_service_order(
        db_session, actor=tecnico, data=ServiceOrderCreate(motivo="Visita")
    )

    base = datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)
    service_order_service.update_service_order(
        db_session, actor=tecnico,
        data=ServiceOrderUpdate(
            servicio_numero=orden.numero,
            hora_salida=base,
            hora_llegada=base + timedelta(hours=1),
            hora_termino=base + timedelta(hours=3),
        ),
    )

    reporte = report_service.generar_reporte_servicios(db_session, actor=jefe)

    assert reporte["cantidad_registros"] == 1
    assert reporte["por_tecnico"].get("TecnicoServ User") == 1
    assert reporte["tiempo_promedio_traslado_horas"] == 1.0
    assert reporte["tiempo_promedio_atencion_horas"] == 2.0
