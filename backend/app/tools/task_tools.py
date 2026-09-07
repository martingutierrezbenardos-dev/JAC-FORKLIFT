from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ValidationDomainError
from app.models.task import Task
from app.models.user import User
from app.schemas.task import CompletarTareaInput, TaskCreate, TaskSearchParams
from app.services import task_service
from app.tools.serialization import to_jsonable


def _serialize_task(task: Task) -> dict:
    return {
        "id": str(task.id),
        "titulo": task.titulo,
        "descripcion": task.descripcion,
        "fecha_limite": to_jsonable(task.fecha_limite),
        "prioridad": to_jsonable(task.prioridad),
        "estado": to_jsonable(task.estado),
        "proyecto": task.proyecto,
    }


def crear_tarea(db: Session, actor: User, data: TaskCreate) -> dict:
    task = task_service.create_task(db, actor=actor, data=data, canal="whatsapp")
    return {"tarea": _serialize_task(task)}


def buscar_tareas(db: Session, actor: User, data: TaskSearchParams) -> dict:
    tasks = task_service.search_tasks(db, actor=actor, params=data)
    return {"cantidad": len(tasks), "tareas": [_serialize_task(t) for t in tasks]}


def completar_tarea(db: Session, actor: User, data: CompletarTareaInput) -> dict:
    if data.tarea_id:
        try:
            task_id = uuid.UUID(data.tarea_id)
        except ValueError as exc:
            raise ValidationDomainError("El identificador de tarea no es válido.") from exc
    elif data.titulo_contiene:
        stmt = (
            select(Task)
            .where(Task.asignado_a == actor.id, Task.deleted_at.is_(None))
            .where(Task.titulo.ilike(f"%{data.titulo_contiene}%"))
        )
        matches = list(db.execute(stmt).scalars().all())
        if not matches:
            raise ValidationDomainError(
                f"No encontré ninguna tarea tuya cuyo título contenga '{data.titulo_contiene}'."
            )
        if len(matches) > 1:
            titulos = ", ".join(f"'{m.titulo}'" for m in matches)
            raise ValidationDomainError(
                f"Encontré varias tareas que coinciden ({titulos}). ¿Cuál de ellas?"
            )
        task_id = matches[0].id
    else:
        raise ValidationDomainError("Necesito el ID de la tarea o parte de su título para completarla.")

    task = task_service.complete_task(db, actor=actor, task_id=task_id, canal="whatsapp")
    return {"tarea": _serialize_task(task)}
