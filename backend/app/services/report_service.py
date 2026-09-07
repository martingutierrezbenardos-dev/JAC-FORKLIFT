from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.core.permissions import Permission, has_permission
from app.models.user import User
from app.schemas.expense import ExpenseSearchParams
from app.schemas.task import TaskSearchParams
from app.services import expense_service, task_service


def generar_reporte_gastos(db: Session, *, actor: User, desde: date | None, hasta: date | None) -> dict:
    params = ExpenseSearchParams(desde=desde, hasta=hasta)
    expenses = expense_service.search_expenses(db, actor=actor, params=params)

    alcance = "empresa completa" if has_permission(actor.rol, Permission.EXPENSES_READ_ALL) else "propio"
    total = sum(float(e.monto) for e in expenses)

    return {
        "alcance": alcance,
        "periodo": {"desde": str(desde) if desde else None, "hasta": str(hasta) if hasta else None},
        "total": total,
        "cantidad_registros": len(expenses),
        "por_categoria": expense_service.total_por_categoria(expenses),
        "registros_usados": [str(e.id) for e in expenses],
    }


def generar_reporte_tareas(db: Session, *, actor: User) -> dict:
    params = TaskSearchParams()
    tasks = task_service.search_tasks(db, actor=actor, params=params)

    alcance = "empresa completa" if has_permission(actor.rol, Permission.TASKS_READ_ALL) else "propio"
    por_estado: dict[str, int] = {}
    for t in tasks:
        por_estado[t.estado.value] = por_estado.get(t.estado.value, 0) + 1

    return {
        "alcance": alcance,
        "cantidad_registros": len(tasks),
        "por_estado": por_estado,
        "registros_usados": [str(t.id) for t in tasks],
    }
