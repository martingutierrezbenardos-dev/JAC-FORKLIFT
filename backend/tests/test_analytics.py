from datetime import date, timedelta

import pytest

from app.core.errors import PermissionDeniedError, ValidationDomainError
from app.core.permissions import UserRole
from app.models.customer import Customer
from app.models.crane import CraneContract, CraneUsage
from app.models.expense import PaymentMethod
from app.schemas.expense import ExpenseCreate
from app.schemas.service_order import ServiceOrderCreate
from app.services import analytics_service, expense_service, service_order_service, task_service
from app.schemas.task import TaskCreate
from app.tools.registry import get_tool, tools_available_to_role
from tests.conftest import make_user


def test_comparar_periodos_gastos_calcula_variacion(db_session):
    admin = make_user(db_session, rol=UserRole.ADMINISTRACION, telefono="+56900333001")
    dia_actual = date(2026, 3, 15)
    dia_anterior = date(2026, 3, 14)

    expense_service.create_expense(
        db_session, actor=admin,
        data=ExpenseCreate(fecha=dia_actual, monto=10000, categoria="repuesto", forma_pago=PaymentMethod.EFECTIVO_PROPIO),
    )
    expense_service.create_expense(
        db_session, actor=admin,
        data=ExpenseCreate(fecha=dia_anterior, monto=6000, categoria="repuesto", forma_pago=PaymentMethod.EFECTIVO_PROPIO),
    )

    resultado = analytics_service.comparar_periodos(
        db_session, actor=admin, tipo="gastos", periodo=None, desde=dia_actual, hasta=dia_actual
    )

    assert resultado["periodo_anterior"] == {"desde": str(dia_anterior), "hasta": str(dia_anterior)}
    assert resultado["valor_actual"] == 10000
    assert resultado["valor_anterior"] == 6000
    assert resultado["variacion"]["absoluta"] == 4000
    assert resultado["variacion"]["porcentaje"] == pytest.approx(66.67, rel=1e-3)


def test_comparar_periodos_sin_datos_anteriores_no_calcula_porcentaje(db_session):
    admin = make_user(db_session, rol=UserRole.ADMINISTRACION, telefono="+56900333002")
    dia = date(2026, 4, 1)

    expense_service.create_expense(
        db_session, actor=admin,
        data=ExpenseCreate(fecha=dia, monto=5000, categoria="peaje", forma_pago=PaymentMethod.EFECTIVO_PROPIO),
    )

    resultado = analytics_service.comparar_periodos(
        db_session, actor=admin, tipo="gastos", periodo=None, desde=dia, hasta=dia
    )

    assert resultado["valor_anterior"] == 0
    assert resultado["variacion"]["porcentaje"] is None
    assert resultado["variacion"]["absoluta"] == 5000


def test_comparar_periodos_tipo_invalido_falla(db_session):
    admin = make_user(db_session, rol=UserRole.ADMINISTRACION, telefono="+56900333003")

    with pytest.raises(ValidationDomainError):
        analytics_service.comparar_periodos(db_session, actor=admin, tipo="clientes", periodo="mes")


def test_comparar_periodos_servicios_filtra_por_fecha(db_session):
    jefe = make_user(db_session, rol=UserRole.JEFE_SERVICIOS_TECNICOS, telefono="+56900333004")
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56900333005", nombre="TecnicoAnalytics")

    dia_actual = date(2026, 5, 10)
    dia_anterior = date(2026, 5, 9)

    orden_actual = service_order_service.create_service_order(
        db_session, actor=tecnico, data=ServiceOrderCreate(motivo="Visita actual")
    )
    orden_actual.fecha = dia_actual
    orden_anterior = service_order_service.create_service_order(
        db_session, actor=tecnico, data=ServiceOrderCreate(motivo="Visita anterior")
    )
    orden_anterior.fecha = dia_anterior
    db_session.flush()

    resultado = analytics_service.comparar_periodos(
        db_session, actor=jefe, tipo="servicios", periodo=None, desde=dia_actual, hasta=dia_actual
    )

    assert resultado["valor_actual"] == 1
    assert resultado["valor_anterior"] == 1
    assert resultado["variacion"]["absoluta"] == 0


def test_comparar_periodos_tareas_filtra_por_fecha_creacion(db_session):
    admin = make_user(db_session, rol=UserRole.ADMINISTRACION, telefono="+56900333006")

    dia_actual = date(2026, 6, 20)
    dia_anterior = date(2026, 6, 19)

    tarea_actual = task_service.create_task(db_session, actor=admin, data=TaskCreate(titulo="Tarea actual"))
    tarea_actual.created_at = tarea_actual.created_at.replace(year=2026, month=6, day=20)
    tarea_anterior = task_service.create_task(db_session, actor=admin, data=TaskCreate(titulo="Tarea anterior"))
    tarea_anterior.created_at = tarea_anterior.created_at.replace(year=2026, month=6, day=19)
    db_session.flush()

    resultado = analytics_service.comparar_periodos(
        db_session, actor=admin, tipo="tareas", periodo=None, desde=dia_actual, hasta=dia_actual
    )

    assert resultado["valor_actual"] == 1
    assert resultado["valor_anterior"] == 1


def test_resumen_ejecutivo_requiere_reports_view_all(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56900333007")

    with pytest.raises(PermissionDeniedError):
        analytics_service.generar_resumen_ejecutivo(db_session, actor=tecnico)


def test_resumen_ejecutivo_agrega_datos_de_todos_los_dominios(db_session):
    admin = make_user(db_session, rol=UserRole.ADMINISTRACION, telefono="+56900333008")
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56900333009", nombre="TecnicoResumen")

    hoy = date.today()
    gasto = expense_service.create_expense(
        db_session, actor=tecnico,
        data=ExpenseCreate(fecha=hoy, monto=15000, categoria="combustible", forma_pago=PaymentMethod.EFECTIVO_PROPIO),
    )
    tarea = task_service.create_task(db_session, actor=tecnico, data=TaskCreate(titulo="Tarea resumen"))
    task_service.complete_task(db_session, actor=tecnico, task_id=tarea.id)
    orden = service_order_service.create_service_order(
        db_session, actor=tecnico, data=ServiceOrderCreate(motivo="Visita resumen")
    )

    cliente = Customer(nombre="Cliente Grúa Resumen")
    db_session.add(cliente)
    db_session.flush()
    contrato = CraneContract(
        cliente_id=cliente.id, periodo_inicio=hoy, periodo_fin=hoy + timedelta(days=30),
        horas_contratadas=100, costo_hora=45000,
    )
    db_session.add(contrato)
    db_session.flush()
    db_session.add(CraneUsage(contrato_id=contrato.id, registrado_por=tecnico.id, fecha=hoy, horas_usadas=90))
    db_session.flush()

    resumen = analytics_service.generar_resumen_ejecutivo(db_session, actor=admin, periodo="mes")

    assert resumen["gastos"]["total"] >= 15000
    assert resumen["tareas"]["completadas"] >= 1
    assert resumen["servicios"]["cantidad"] >= 1
    assert resumen["gruas"]["contratos_por_agotarse"] >= 1
    assert str(gasto.id) in resumen["registros_usados"]
    assert str(orden.id) in resumen["registros_usados"]


def test_tools_comparar_periodo_y_resumen_ejecutivo_registradas_con_permisos_correctos():
    tool_comparar = get_tool("comparar_periodo")
    tool_resumen = get_tool("generar_resumen_ejecutivo")

    assert tool_comparar is not None
    assert tool_resumen is not None

    tools_marketing = {t.name for t in tools_available_to_role(UserRole.GERENTE_MARKETING)}
    assert "comparar_periodo" in tools_marketing
    assert "generar_resumen_ejecutivo" not in tools_marketing

    tools_admin = {t.name for t in tools_available_to_role(UserRole.ADMINISTRACION)}
    assert "generar_resumen_ejecutivo" in tools_admin
