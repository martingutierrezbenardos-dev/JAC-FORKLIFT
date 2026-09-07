from datetime import date

import pytest

from app.core.errors import PermissionDeniedError, ValidationDomainError
from app.core.permissions import UserRole
from app.models.expense import PaymentMethod, ReimbursementStatus
from app.schemas.expense import ExpenseCreate, ExpenseSearchParams, ExpenseUpdate
from app.services import expense_service
from tests.conftest import make_user


def test_crear_gasto_infiere_requiere_reembolso_desde_forma_pago(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56933333331")

    gasto = expense_service.create_expense(
        db_session,
        actor=tecnico,
        data=ExpenseCreate(
            fecha=date.today(), monto=85000, categoria="repuesto", proveedor="Repuestos X",
            forma_pago=PaymentMethod.EFECTIVO_PROPIO,
        ),
    )

    assert gasto.requiere_reembolso is True
    assert gasto.estado_reembolso == ReimbursementStatus.PENDIENTE
    assert gasto.user_id == tecnico.id
    assert gasto.pagado_por == tecnico.id


def test_crear_gasto_con_tarjeta_empresa_no_requiere_reembolso(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56933333332")

    gasto = expense_service.create_expense(
        db_session,
        actor=tecnico,
        data=ExpenseCreate(
            fecha=date.today(), monto=20000, categoria="combustible", forma_pago=PaymentMethod.TARJETA_EMPRESA
        ),
    )

    assert gasto.requiere_reembolso is False
    assert gasto.estado_reembolso is None


def test_crear_gasto_con_cliente_inexistente_falla(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56933333333")

    with pytest.raises(ValidationDomainError):
        expense_service.create_expense(
            db_session,
            actor=tecnico,
            data=ExpenseCreate(
                fecha=date.today(), monto=1000, categoria="otros",
                forma_pago=PaymentMethod.EFECTIVO_PROPIO, cliente_nombre="Cliente Que No Existe",
            ),
        )


def test_tecnico_sin_permiso_no_puede_aprobar_reembolso(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56933333334")

    gasto = expense_service.create_expense(
        db_session,
        actor=tecnico,
        data=ExpenseCreate(
            fecha=date.today(), monto=5000, categoria="peaje", forma_pago=PaymentMethod.EFECTIVO_PROPIO
        ),
    )

    with pytest.raises(PermissionDeniedError):
        expense_service.update_expense(
            db_session, actor=tecnico, expense_id=gasto.id,
            data=ExpenseUpdate(estado_reembolso=ReimbursementStatus.PAGADO),
        )


def test_administracion_puede_aprobar_reembolso(db_session):
    admin = make_user(db_session, rol=UserRole.ADMINISTRACION, telefono="+56933333335")
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56933333336", nombre="Tecnico2")

    gasto = expense_service.create_expense(
        db_session,
        actor=tecnico,
        data=ExpenseCreate(
            fecha=date.today(), monto=7000, categoria="peaje", forma_pago=PaymentMethod.EFECTIVO_PROPIO
        ),
    )

    actualizado = expense_service.update_expense(
        db_session, actor=admin, expense_id=gasto.id,
        data=ExpenseUpdate(estado_reembolso=ReimbursementStatus.APROBADO),
    )

    assert actualizado.estado_reembolso == ReimbursementStatus.APROBADO


def test_buscar_gastos_filtra_por_categoria(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56933333337")
    expense_service.create_expense(
        db_session, actor=tecnico,
        data=ExpenseCreate(fecha=date.today(), monto=1000, categoria="peaje", forma_pago=PaymentMethod.TARJETA_EMPRESA),
    )
    expense_service.create_expense(
        db_session, actor=tecnico,
        data=ExpenseCreate(fecha=date.today(), monto=2000, categoria="combustible", forma_pago=PaymentMethod.TARJETA_EMPRESA),
    )

    resultados = expense_service.search_expenses(
        db_session, actor=tecnico, params=ExpenseSearchParams(categoria="peaje")
    )

    assert len(resultados) == 1
    assert resultados[0].categoria.value == "peaje"
