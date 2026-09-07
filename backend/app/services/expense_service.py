from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, PermissionDeniedError, ValidationDomainError
from app.core.permissions import Permission, UserRole, has_permission
from app.models.expense import Expense, PaymentMethod, ReimbursementStatus
from app.models.user import User
from app.schemas.expense import ExpenseCreate, ExpenseSearchParams, ExpenseUpdate
from app.services import audit_service, user_service
from app.services.lookup_service import resolve_customer_by_name, resolve_machine_by_number


def create_expense(db: Session, *, actor: User, data: ExpenseCreate, canal: str = "whatsapp") -> Expense:
    """Crea un gasto para ``actor``. ``actor`` es siempre quien registra (nunca se acepta un
    ``user_id`` arbitrario del exterior, por diseño — ver docs/ai-tools.md)."""
    if not has_permission(actor.rol, Permission.EXPENSES_CREATE_OWN):
        raise PermissionDeniedError("No tienes permiso para registrar gastos.")

    customer = resolve_customer_by_name(db, data.cliente_nombre)
    if data.cliente_nombre and customer is None:
        raise ValidationDomainError(f"No encontré ningún cliente llamado '{data.cliente_nombre}'.")

    machine = resolve_machine_by_number(db, data.maquina_numero)
    if data.maquina_numero and machine is None:
        raise ValidationDomainError(f"No encontré ninguna máquina con número '{data.maquina_numero}'.")

    pagado_por_id = actor.id
    if data.pagado_por_telefono:
        payer = user_service.get_by_phone(db, data.pagado_por_telefono)
        if payer is None:
            raise ValidationDomainError("No encontré a la persona que indicaste como quien pagó.")
        pagado_por_id = payer.id

    requiere_reembolso = data.requiere_reembolso
    if requiere_reembolso is None:
        requiere_reembolso = data.forma_pago == PaymentMethod.EFECTIVO_PROPIO

    expense = Expense(
        user_id=actor.id,
        created_by=actor.id,
        fecha=data.fecha,
        monto=data.monto,
        moneda=data.moneda,
        categoria=data.categoria,
        proveedor=data.proveedor,
        descripcion=data.descripcion,
        cliente_id=customer.id if customer else None,
        maquina_id=machine.id if machine else None,
        forma_pago=data.forma_pago,
        pagado_por=pagado_por_id,
        requiere_reembolso=requiere_reembolso,
        estado_reembolso=ReimbursementStatus.PENDIENTE if requiere_reembolso else None,
        comprobante_url=data.comprobante_url,
        observaciones=data.observaciones,
    )
    db.add(expense)
    db.flush()

    audit_service.record(
        db,
        usuario_id=actor.id,
        accion="create",
        entidad="expenses",
        entidad_id=expense.id,
        datos_nuevos={"monto": str(expense.monto), "categoria": expense.categoria.value},
        canal=canal,
    )
    return expense


def search_expenses(db: Session, *, actor: User, params: ExpenseSearchParams) -> list[Expense]:
    stmt = select(Expense).where(Expense.deleted_at.is_(None))

    target_user_id: uuid.UUID | None = actor.id
    if params.usuario_telefono:
        if not has_permission(actor.rol, Permission.EXPENSES_READ_ALL):
            # Se ignora silenciosamente el filtro pedido: el usuario no puede ver gastos
            # ajenos, sin importar lo que haya escrito. Ver docs/security.md.
            target_user_id = actor.id
        else:
            other = user_service.get_by_phone(db, params.usuario_telefono)
            target_user_id = other.id if other else uuid.uuid4()  # UUID inexistente -> 0 resultados
    elif not has_permission(actor.rol, Permission.EXPENSES_READ_ALL):
        target_user_id = actor.id
    else:
        target_user_id = None  # con permiso ALL y sin filtro de usuario, se ve todo

    if target_user_id is not None:
        stmt = stmt.where(Expense.user_id == target_user_id)
    if params.desde:
        stmt = stmt.where(Expense.fecha >= params.desde)
    if params.hasta:
        stmt = stmt.where(Expense.fecha <= params.hasta)
    if params.categoria:
        stmt = stmt.where(Expense.categoria == params.categoria)
    if params.proveedor:
        stmt = stmt.where(Expense.proveedor.ilike(f"%{params.proveedor}%"))
    if params.estado_reembolso:
        stmt = stmt.where(Expense.estado_reembolso == params.estado_reembolso)

    stmt = stmt.order_by(Expense.fecha.desc())
    return list(db.execute(stmt).scalars().all())


def get_expense(db: Session, expense_id: uuid.UUID) -> Expense:
    expense = db.get(Expense, expense_id)
    if expense is None or expense.deleted_at is not None:
        raise NotFoundError("Gasto no encontrado.")
    return expense


def update_expense(
    db: Session, *, actor: User, expense_id: uuid.UUID, data: ExpenseUpdate, canal: str = "whatsapp"
) -> Expense:
    expense = get_expense(db, expense_id)

    is_own = expense.user_id == actor.id
    if is_own and not has_permission(actor.rol, Permission.EXPENSES_UPDATE_OWN):
        raise PermissionDeniedError("No tienes permiso para modificar tus gastos.")
    if not is_own and not has_permission(actor.rol, Permission.EXPENSES_UPDATE_ALL):
        raise PermissionDeniedError("No puedes modificar gastos de otra persona.")

    if data.estado_reembolso is not None and not has_permission(
        actor.rol, Permission.EXPENSES_APPROVE_REIMBURSEMENT
    ):
        raise PermissionDeniedError(
            "No tienes permiso para cambiar el estado de reembolso de un gasto."
        )

    datos_anteriores = {
        "monto": str(expense.monto),
        "categoria": expense.categoria.value,
        "estado_reembolso": expense.estado_reembolso.value if expense.estado_reembolso else None,
    }

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(expense, field, value)
    db.flush()

    audit_service.record(
        db,
        usuario_id=actor.id,
        accion="update",
        entidad="expenses",
        entidad_id=expense.id,
        datos_anteriores=datos_anteriores,
        datos_nuevos=data.model_dump(exclude_unset=True, mode="json"),
        canal=canal,
    )
    return expense


def total_por_categoria(expenses: list[Expense]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for e in expenses:
        key = e.categoria.value
        totals[key] = totals.get(key, 0.0) + float(e.monto)
    return totals
