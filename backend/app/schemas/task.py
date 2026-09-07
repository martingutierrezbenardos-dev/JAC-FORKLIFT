from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.task import TaskPriority, TaskStatus


class TaskCreate(BaseModel):
    titulo: str = Field(min_length=3, max_length=200)
    descripcion: str | None = None
    asignado_a_telefono: str | None = Field(
        default=None,
        description="Teléfono WhatsApp de a quién se asigna. Si se omite, se asigna a quien escribe.",
    )
    fecha_limite: datetime | None = None
    prioridad: TaskPriority = TaskPriority.MEDIA
    proyecto: str | None = None


class TaskUpdate(BaseModel):
    titulo: str | None = None
    descripcion: str | None = None
    fecha_limite: datetime | None = None
    prioridad: TaskPriority | None = None
    estado: TaskStatus | None = None


class CompletarTareaInput(BaseModel):
    tarea_id: str | None = Field(default=None, description="ID de la tarea a completar.")
    titulo_contiene: str | None = Field(
        default=None,
        description="Si no se conoce el ID, texto que debería estar contenido en el título de la tarea.",
    )


class TaskSearchParams(BaseModel):
    estado: TaskStatus | None = None
    asignado_a_telefono: str | None = None
    fecha_limite_antes: datetime | None = None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    titulo: str
    descripcion: str | None
    asignado_a: uuid.UUID
    creado_por: uuid.UUID
    fecha_limite: datetime | None
    prioridad: TaskPriority
    estado: TaskStatus
    proyecto: str | None
    created_at: datetime
    updated_at: datetime
