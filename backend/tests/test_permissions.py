import pytest

from app.core.permissions import Permission, UserRole, get_permissions_for_role, has_permission
from app.core.errors import PermissionDeniedError
from app.models.expense import PaymentMethod
from app.schemas.expense import ExpenseCreate, ExpenseSearchParams
from app.services import expense_service
from datetime import date

from tests.conftest import make_user


def test_tecnico_has_only_own_scope_permissions():
    perms = get_permissions_for_role(UserRole.TECNICO)
    assert Permission.EXPENSES_CREATE_OWN in perms
    assert Permission.EXPENSES_READ_OWN in perms
    assert Permission.EXPENSES_READ_ALL not in perms
    assert Permission.USERS_MANAGE not in perms


def test_gerente_general_has_almost_everything_except_user_management():
    perms = get_permissions_for_role(UserRole.GERENTE_GENERAL)
    assert Permission.EXPENSES_READ_ALL in perms
    assert Permission.REPORTS_VIEW_ALL in perms
    assert Permission.USERS_MANAGE not in perms  # reservado a admin_sistema


def test_admin_sistema_has_every_permission():
    perms = get_permissions_for_role(UserRole.ADMIN_SISTEMA)
    assert perms == set(Permission)


def test_gerente_marketing_has_no_expense_permissions():
    assert not has_permission(UserRole.GERENTE_MARKETING, Permission.EXPENSES_CREATE_OWN)
    assert not has_permission(UserRole.GERENTE_MARKETING, Permission.EXPENSES_READ_OWN)


def test_tecnico_cannot_see_other_users_expenses_even_if_requested(db_session):
    """Aunque el técnico pida explícitamente los gastos de otra persona, el servicio debe
    forzar el filtro a sus propios gastos (doble verificación, ver docs/security.md)."""
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56922222221")
    otro = make_user(db_session, rol=UserRole.TECNICO, telefono="+56922222222", nombre="Otro")

    expense_service.create_expense(
        db_session,
        actor=otro,
        data=ExpenseCreate(
            fecha=date.today(), monto=10000, categoria="combustible", forma_pago=PaymentMethod.EFECTIVO_PROPIO
        ),
    )

    resultados = expense_service.search_expenses(
        db_session, actor=tecnico, params=ExpenseSearchParams(usuario_telefono=otro.telefono_whatsapp)
    )

    assert resultados == []  # el filtro pedido se ignora; el técnico solo ve lo suyo (nada, en este caso)


def test_administracion_can_see_other_users_expenses(db_session):
    admin = make_user(db_session, rol=UserRole.ADMINISTRACION, telefono="+56922222223")
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56922222224", nombre="Tecnico")

    expense_service.create_expense(
        db_session,
        actor=tecnico,
        data=ExpenseCreate(
            fecha=date.today(), monto=15000, categoria="combustible", forma_pago=PaymentMethod.EFECTIVO_PROPIO
        ),
    )

    resultados = expense_service.search_expenses(
        db_session, actor=admin, params=ExpenseSearchParams(usuario_telefono=tecnico.telefono_whatsapp)
    )

    assert len(resultados) == 1


def test_tecnico_cannot_update_others_expense(db_session):
    from app.schemas.expense import ExpenseUpdate

    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56922222225")
    otro = make_user(db_session, rol=UserRole.TECNICO, telefono="+56922222226", nombre="Otro")

    expense = expense_service.create_expense(
        db_session,
        actor=otro,
        data=ExpenseCreate(
            fecha=date.today(), monto=5000, categoria="peaje", forma_pago=PaymentMethod.TARJETA_EMPRESA
        ),
    )

    with pytest.raises(PermissionDeniedError):
        expense_service.update_expense(
            db_session, actor=tecnico, expense_id=expense.id, data=ExpenseUpdate(monto=9999)
        )
