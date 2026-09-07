"""Catálogo de herramientas del agente de IA.

Cada ``ToolDefinition`` conecta: (a) el nombre y schema que ve el LLM, (b) el permiso mínimo
requerido para siquiera intentar la operación, (c) el nivel de confirmación (ver
docs/architecture.md §4), y (d) el handler real, que SIEMPRE delega en ``app/services/*``.
El LLM nunca ejecuta código directamente: solo puede pedir, por nombre, una de estas
herramientas, con argumentos validados por Pydantic antes de llegar al handler.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.permissions import Permission, UserRole, has_permission
from app.models.user import User
from app.schemas.expense import ExpenseCreate, ExpenseSearchParams, ExpenseUpdateToolInput
from app.schemas.task import CompletarTareaInput, TaskCreate, TaskSearchParams
from app.schemas.user import BuscarUsuarioInput
from app.tools import expense_tools, report_tools, task_tools, user_tools

ConfirmationLevelFn = Callable[[BaseModel, User], int]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_model: type[BaseModel]
    handler: Callable[[Session, User, BaseModel], dict[str, Any]]
    required_permission: Permission | None
    confirmation_level: int | ConfirmationLevelFn = 1

    def confirmation_level_for(self, validated_input: BaseModel, actor: User) -> int:
        if callable(self.confirmation_level):
            return self.confirmation_level(validated_input, actor)
        return self.confirmation_level

    def to_llm_schema(self) -> dict[str, Any]:
        schema = self.input_model.model_json_schema()
        schema.pop("title", None)
        schema.setdefault("properties", {})
        for prop in schema["properties"].values():
            prop.pop("title", None)
        return {"name": self.name, "description": self.description, "input_schema": schema}


def _crear_tarea_confirmation_level(data: BaseModel, actor: User) -> int:
    assert isinstance(data, TaskCreate)
    if not data.asignado_a_telefono or data.asignado_a_telefono == actor.telefono_whatsapp:
        return 1
    assignee = None
    # No tenemos sesión de DB aquí; la asignación a uno mismo ya cubre el caso común.
    # Si el teléfono difiere del de quien escribe, se trata como asignación a un tercero.
    return 2


REGISTRY: dict[str, ToolDefinition] = {
    "buscar_usuario": ToolDefinition(
        name="buscar_usuario",
        description="Busca datos básicos de un usuario interno por nombre o teléfono de WhatsApp.",
        input_model=BuscarUsuarioInput,
        handler=user_tools.buscar_usuario,
        required_permission=None,
        confirmation_level=1,
    ),
    "crear_gasto": ToolDefinition(
        name="crear_gasto",
        description=(
            "Registra un gasto para la persona que escribe (nunca para otra persona). Usa "
            "esto cuando alguien mencione haber comprado algo, pagado algo, o incurrido en "
            "un costo relacionado con el trabajo."
        ),
        input_model=ExpenseCreate,
        handler=expense_tools.crear_gasto,
        required_permission=Permission.EXPENSES_CREATE_OWN,
        confirmation_level=1,
    ),
    "buscar_gastos": ToolDefinition(
        name="buscar_gastos",
        description=(
            "Busca gastos registrados con filtros opcionales de fecha, categoría, proveedor "
            "o estado de reembolso. Si quien pregunta no tiene permiso para ver los gastos de "
            "toda la empresa, automáticamente solo se le muestran los propios."
        ),
        input_model=ExpenseSearchParams,
        handler=expense_tools.buscar_gastos,
        required_permission=Permission.EXPENSES_READ_OWN,
        confirmation_level=1,
    ),
    "actualizar_gasto": ToolDefinition(
        name="actualizar_gasto",
        description=(
            "Modifica campos de un gasto existente (monto, categoría, proveedor, "
            "descripción, estado de reembolso, observaciones). Requiere confirmación del "
            "usuario antes de aplicarse."
        ),
        input_model=ExpenseUpdateToolInput,
        handler=expense_tools.actualizar_gasto,
        required_permission=Permission.EXPENSES_UPDATE_OWN,
        confirmation_level=2,
    ),
    "crear_tarea": ToolDefinition(
        name="crear_tarea",
        description=(
            "Crea una tarea. Si no se indica a quién se asigna, se asigna a quien escribe. "
            "Asignar una tarea a otra persona requiere confirmación."
        ),
        input_model=TaskCreate,
        handler=task_tools.crear_tarea,
        required_permission=Permission.TASKS_CREATE_OWN,
        confirmation_level=_crear_tarea_confirmation_level,
    ),
    "buscar_tareas": ToolDefinition(
        name="buscar_tareas",
        description="Busca tareas con filtros opcionales de estado, responsable o fecha límite.",
        input_model=TaskSearchParams,
        handler=task_tools.buscar_tareas,
        required_permission=Permission.TASKS_READ_OWN,
        confirmation_level=1,
    ),
    "completar_tarea": ToolDefinition(
        name="completar_tarea",
        description="Marca una tarea como completada, identificándola por ID o por parte de su título.",
        input_model=CompletarTareaInput,
        handler=task_tools.completar_tarea,
        required_permission=Permission.TASKS_COMPLETE_OWN,
        confirmation_level=1,
    ),
    "generar_reporte": ToolDefinition(
        name="generar_reporte",
        description=(
            "Genera un resumen agregado de gastos o tareas para un período. El alcance "
            "(propio o de toda la empresa) depende de los permisos de quien pregunta."
        ),
        input_model=report_tools.GenerarReporteInput,
        handler=report_tools.generar_reporte,
        required_permission=Permission.REPORTS_VIEW_OWN,
        confirmation_level=1,
    ),
}


def get_tool(name: str) -> ToolDefinition | None:
    return REGISTRY.get(name)


def tools_available_to_role(role: UserRole) -> list[ToolDefinition]:
    return [t for t in REGISTRY.values() if t.required_permission is None or has_permission(role, t.required_permission)]


def llm_schemas_for_role(role: UserRole) -> list[dict[str, Any]]:
    return [t.to_llm_schema() for t in tools_available_to_role(role)]
