from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, PermissionDeniedError, ValidationDomainError
from app.core.permissions import Permission, has_permission
from app.models.task import Task, TaskStatus
from app.models.user import User
from app.schemas.task import TaskCreate, TaskSearchParams, TaskUpdate
from app.services import audit_service, user_service


def create_task(db: Session, *, actor: User, data: TaskCreate, canal: str = "whatsapp") -> Task:
    assignee = actor
    assigning_to_other = False
    if data.asignado_a_telefono and data.asignado_a_telefono != actor.telefono_whatsapp:
        found = user_service.get_by_phone(db, data.asignado_a_telefono)
        if found is None:
            raise ValidationDomainError("No encontré a la persona a quien quieres asignar la tarea.")
        assignee = found
        assigning_to_other = True

    if assigning_to_other:
        if not has_permission(actor.rol, Permission.TASKS_ASSIGN_OTHERS):
            raise PermissionDeniedError("No tienes permiso para asignar tareas a otras personas.")
    elif not has_permission(actor.rol, Permission.TASKS_CREATE_OWN):
        raise PermissionDeniedError("No tienes permiso para crear tareas.")

    task = Task(
        titulo=data.titulo,
        descripcion=data.descripcion,
        asignado_a=assignee.id,
        creado_por=actor.id,
        fecha_limite=data.fecha_limite,
        prioridad=data.prioridad,
        proyecto=data.proyecto,
    )
    db.add(task)
    db.flush()

    audit_service.record(
        db,
        usuario_id=actor.id,
        accion="create",
        entidad="tasks",
        entidad_id=task.id,
        datos_nuevos={"titulo": task.titulo, "asignado_a": str(task.asignado_a)},
        canal=canal,
    )
    return task


def search_tasks(db: Session, *, actor: User, params: TaskSearchParams) -> list[Task]:
    stmt = select(Task).where(Task.deleted_at.is_(None))

    target_user_id: uuid.UUID | None = actor.id
    if params.asignado_a_telefono:
        if not has_permission(actor.rol, Permission.TASKS_READ_ALL):
            target_user_id = actor.id
        else:
            other = user_service.get_by_phone(db, params.asignado_a_telefono)
            target_user_id = other.id if other else uuid.uuid4()
    elif not has_permission(actor.rol, Permission.TASKS_READ_ALL):
        target_user_id = actor.id
    else:
        target_user_id = None

    if target_user_id is not None:
        stmt = stmt.where(Task.asignado_a == target_user_id)
    if params.estado:
        stmt = stmt.where(Task.estado == params.estado)
    if params.fecha_limite_antes:
        stmt = stmt.where(Task.fecha_limite <= params.fecha_limite_antes)

    stmt = stmt.order_by(Task.fecha_limite.asc().nulls_last())
    return list(db.execute(stmt).scalars().all())


def get_task(db: Session, task_id: uuid.UUID) -> Task:
    task = db.get(Task, task_id)
    if task is None or task.deleted_at is not None:
        raise NotFoundError("Tarea no encontrada.")
    return task


def complete_task(db: Session, *, actor: User, task_id: uuid.UUID, canal: str = "whatsapp") -> Task:
    task = get_task(db, task_id)
    is_own = task.asignado_a == actor.id

    if is_own and not has_permission(actor.rol, Permission.TASKS_COMPLETE_OWN):
        raise PermissionDeniedError("No tienes permiso para completar tareas.")
    if not is_own and not has_permission(actor.rol, Permission.TASKS_COMPLETE_ALL):
        raise PermissionDeniedError("No puedes completar una tarea asignada a otra persona.")

    estado_anterior = task.estado.value
    task.estado = TaskStatus.COMPLETADA
    db.flush()

    audit_service.record(
        db,
        usuario_id=actor.id,
        accion="update",
        entidad="tasks",
        entidad_id=task.id,
        datos_anteriores={"estado": estado_anterior},
        datos_nuevos={"estado": task.estado.value},
        canal=canal,
    )
    return task


def update_task(db: Session, *, actor: User, task_id: uuid.UUID, data: TaskUpdate, canal: str = "whatsapp") -> Task:
    task = get_task(db, task_id)
    is_own_created = task.creado_por == actor.id
    if not is_own_created and not has_permission(actor.rol, Permission.TASKS_ASSIGN_OTHERS):
        raise PermissionDeniedError("No tienes permiso para modificar esta tarea.")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    db.flush()

    audit_service.record(
        db,
        usuario_id=actor.id,
        accion="update",
        entidad="tasks",
        entidad_id=task.id,
        datos_nuevos=data.model_dump(exclude_unset=True, mode="json"),
        canal=canal,
    )
    return task
