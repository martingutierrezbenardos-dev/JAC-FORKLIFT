from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import domain_errors_as_http
from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.task import TaskStatus
from app.models.user import User
from app.schemas.task import TaskCreate, TaskOut, TaskSearchParams, TaskUpdate
from app.services import task_service

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskOut])
def search_tasks(
    estado: TaskStatus | None = None,
    asignado_a_telefono: str | None = None,
    fecha_limite_antes: datetime | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TaskOut]:
    params = TaskSearchParams(
        estado=estado, asignado_a_telefono=asignado_a_telefono, fecha_limite_antes=fecha_limite_antes
    )
    with domain_errors_as_http():
        return list(task_service.search_tasks(db, actor=current_user, params=params))


@router.post("", response_model=TaskOut, status_code=201)
def create_task(
    payload: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskOut:
    with domain_errors_as_http():
        task = task_service.create_task(db, actor=current_user, data=payload, canal="web")
        db.commit()
    return task


@router.post("/{task_id}/completar", response_model=TaskOut)
def complete_task(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskOut:
    with domain_errors_as_http():
        task = task_service.complete_task(db, actor=current_user, task_id=task_id, canal="web")
        db.commit()
    return task


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: uuid.UUID,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskOut:
    with domain_errors_as_http():
        task = task_service.update_task(db, actor=current_user, task_id=task_id, data=payload, canal="web")
        db.commit()
    return task
