from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ValidationDomainError
from app.models.expense import Expense
from app.models.user import User
from app.schemas.expense import ExpenseCreate, ExpenseSearchParams, ExpenseUpdate, ExpenseUpdateToolInput
from app.services import expense_service
from app.tools.serialization import to_jsonable


def _serialize_expense(expense: Expense) -> dict:
    return {
        "id": str(expense.id),
        "fecha": to_jsonable(expense.fecha),
        "monto": to_jsonable(expense.monto),
        "moneda": to_jsonable(expense.moneda),
        "categoria": to_jsonable(expense.categoria),
        "proveedor": expense.proveedor,
        "descripcion": expense.descripcion,
        "forma_pago": to_jsonable(expense.forma_pago),
        "requiere_reembolso": expense.requiere_reembolso,
        "estado_reembolso": to_jsonable(expense.estado_reembolso),
    }


def crear_gasto(db: Session, actor: User, data: ExpenseCreate) -> dict:
    expense = expense_service.create_expense(db, actor=actor, data=data, canal="whatsapp")
    return {"gasto": _serialize_expense(expense)}


def buscar_gastos(db: Session, actor: User, data: ExpenseSearchParams) -> dict:
    expenses = expense_service.search_expenses(db, actor=actor, params=data)
    return {
        "cantidad": len(expenses),
        "total": to_jsonable(sum((e.monto for e in expenses), start=0)),
        "gastos": [_serialize_expense(e) for e in expenses],
    }


def actualizar_gasto(db: Session, actor: User, data: ExpenseUpdateToolInput) -> dict:
    if data.gasto_id:
        try:
            expense_id = uuid.UUID(data.gasto_id)
        except ValueError as exc:
            raise ValidationDomainError("El identificador de gasto no es válido.") from exc
    else:
        stmt = (
            select(Expense)
            .where(Expense.user_id == actor.id, Expense.deleted_at.is_(None))
            .order_by(Expense.created_at.desc())
            .limit(1)
        )
        latest = db.execute(stmt).scalars().first()
        if latest is None:
            raise ValidationDomainError("No encontré ningún gasto tuyo para modificar.")
        expense_id = latest.id

    update_fields = data.model_dump(exclude={"gasto_id"}, exclude_unset=True)
    expense = expense_service.update_expense(
        db, actor=actor, expense_id=expense_id, data=ExpenseUpdate(**update_fields), canal="whatsapp"
    )
    return {"gasto": _serialize_expense(expense)}
