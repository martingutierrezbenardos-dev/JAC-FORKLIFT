from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import domain_errors_as_http
from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.expense import ExpenseCategory, ReimbursementStatus
from app.models.user import User
from app.schemas.expense import ExpenseCreate, ExpenseOut, ExpenseSearchParams, ExpenseUpdate
from app.services import expense_service

router = APIRouter(prefix="/api/expenses", tags=["expenses"])


@router.get("", response_model=list[ExpenseOut])
def search_expenses(
    desde: date | None = None,
    hasta: date | None = None,
    categoria: ExpenseCategory | None = None,
    proveedor: str | None = None,
    estado_reembolso: ReimbursementStatus | None = None,
    usuario_telefono: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ExpenseOut]:
    params = ExpenseSearchParams(
        desde=desde,
        hasta=hasta,
        categoria=categoria,
        proveedor=proveedor,
        estado_reembolso=estado_reembolso,
        usuario_telefono=usuario_telefono,
    )
    with domain_errors_as_http():
        return list(expense_service.search_expenses(db, actor=current_user, params=params))


@router.post("", response_model=ExpenseOut, status_code=201)
def create_expense(
    payload: ExpenseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExpenseOut:
    with domain_errors_as_http():
        expense = expense_service.create_expense(db, actor=current_user, data=payload, canal="web")
        db.commit()
    return expense


@router.patch("/{expense_id}", response_model=ExpenseOut)
def update_expense(
    expense_id: uuid.UUID,
    payload: ExpenseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExpenseOut:
    with domain_errors_as_http():
        expense = expense_service.update_expense(
            db, actor=current_user, expense_id=expense_id, data=payload, canal="web"
        )
        db.commit()
    return expense
