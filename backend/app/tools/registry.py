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
from app.models.service_order import ServiceOrderStatus
from app.models.user import User
from app.schemas.calendar import ConsultarCalendarioInput, CrearReunionInput
from app.schemas.crane import ConsultarHorasGruaInput, RegistrarUsoGruaInput
from app.schemas.customer import BuscarClienteInput
from app.schemas.email import BuscarCorreosInput, EnviarCorreoInput, PrepararCorreoInput
from app.schemas.expense import ExpenseCreate, ExpenseSearchParams, ExpenseUpdateToolInput
from app.schemas.machine import BuscarMaquinaInput
from app.schemas.maintenance import MaintenanceAlertParams, MaintenanceCreate, MaintenanceSearchParams
from app.schemas.service_order import ServiceOrderCreate, ServiceOrderSearchParams, ServiceOrderUpdate
from app.schemas.task import CompletarTareaInput, TaskCreate, TaskSearchParams
from app.schemas.user import BuscarUsuarioInput
from app.schemas.vehicle import BuscarVehiculoInput, ConsultarRangoVehiculoInput, ConsultarUbicacionVehiculoInput
from app.tools import (
    calendar_tools,
    crane_tools,
    customer_tools,
    email_tools,
    expense_tools,
    machine_tools,
    maintenance_tools,
    report_tools,
    service_tools,
    task_tools,
    user_tools,
    vehicle_tools,
)

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


def _actualizar_servicio_confirmation_level(data: BaseModel, actor: User) -> int:
    assert isinstance(data, ServiceOrderUpdate)
    # Cerrar una orden de servicio es una acción más definitiva; el resto de campos
    # (horas, diagnóstico, trabajo realizado) son el reporte natural y frecuente del técnico
    # y no deben interrumpirse con una confirmación (ver sección 7 del brief).
    if data.estado == ServiceOrderStatus.CERRADO:
        return 2
    return 1


def _crear_reunion_confirmation_level(data: BaseModel, actor: User) -> int:
    assert isinstance(data, CrearReunionInput)
    # Una reunión que involucra a otras personas siempre requiere confirmación (sección 13
    # del brief: "verificar disponibilidad y pedir confirmación cuando sea necesario"). Un
    # bloqueo puramente personal en el propio calendario no necesita fricción.
    return 2 if data.participantes_telefonos else 1


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
            "un costo relacionado con el trabajo. Si el contexto incluye una URL de "
            "comprobante ya guardada (mensaje del tipo '[La foto quedó guardada en ...]'), "
            "pásala en comprobante_url."
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
            "Genera un resumen agregado de gastos, tareas o servicios técnicos para un "
            "período (día, semana, mes, o un rango de fechas explícito), con desgloses por "
            "categoría, trabajador, proveedor, cliente, máquina o sucursal según corresponda. "
            "El alcance (propio o de toda la empresa) depende de los permisos de quien pregunta."
        ),
        input_model=report_tools.GenerarReporteInput,
        handler=report_tools.generar_reporte,
        required_permission=Permission.REPORTS_VIEW_OWN,
        confirmation_level=1,
    ),
    "crear_servicio": ToolDefinition(
        name="crear_servicio",
        description=(
            "Crea una nueva orden de servicio técnico para quien escribe (una visita a un "
            "cliente para revisar o reparar una máquina). Usa esto cuando un técnico avise "
            "que va a atender o está atendiendo a un cliente."
        ),
        input_model=ServiceOrderCreate,
        handler=service_tools.crear_servicio,
        required_permission=Permission.SERVICES_CREATE_OWN,
        confirmation_level=1,
    ),
    "actualizar_servicio": ToolDefinition(
        name="actualizar_servicio",
        description=(
            "Actualiza la orden de servicio técnico abierta de quien escribe (o la que se "
            "indique por número): horas de salida/llegada/inicio/término, cliente, máquina, "
            "diagnóstico, trabajo realizado, repuestos utilizados, observaciones o estado. "
            "Usa esto para reportes como 'salí a las 8:30', 'llegué donde el cliente', "
            "'estoy atendiendo la máquina 33' o 'terminé, era el alternador'."
        ),
        input_model=ServiceOrderUpdate,
        handler=service_tools.actualizar_servicio,
        required_permission=Permission.SERVICES_UPDATE_OWN,
        confirmation_level=_actualizar_servicio_confirmation_level,
    ),
    "buscar_servicios": ToolDefinition(
        name="buscar_servicios",
        description="Busca órdenes de servicio técnico con filtros de estado, técnico o cliente.",
        input_model=ServiceOrderSearchParams,
        handler=service_tools.buscar_servicios,
        required_permission=Permission.SERVICES_READ_OWN,
        confirmation_level=1,
    ),
    "buscar_cliente": ToolDefinition(
        name="buscar_cliente",
        description="Busca la ficha de un cliente por nombre (dirección, contacto, tipo, estado).",
        input_model=BuscarClienteInput,
        handler=customer_tools.buscar_cliente,
        required_permission=Permission.CUSTOMERS_READ,
        confirmation_level=1,
    ),
    "buscar_maquina": ToolDefinition(
        name="buscar_maquina",
        description=(
            "Busca la ficha de una máquina por su número interno (marca, modelo, cliente "
            "asociado, horómetro, estado, ubicación)."
        ),
        input_model=BuscarMaquinaInput,
        handler=machine_tools.buscar_maquina,
        required_permission=Permission.MACHINES_READ,
        confirmation_level=1,
    ),
    "crear_mantenimiento": ToolDefinition(
        name="crear_mantenimiento",
        description=(
            "Registra un mantenimiento (preventivo o correctivo) realizado a una máquina: "
            "horómetro, trabajos realizados, repuestos, y opcionalmente cuándo corresponde "
            "el próximo. Actualiza automáticamente la ficha de la máquina."
        ),
        input_model=MaintenanceCreate,
        handler=maintenance_tools.crear_mantenimiento,
        required_permission=Permission.MAINTENANCE_CREATE,
        confirmation_level=1,
    ),
    "buscar_mantenimientos": ToolDefinition(
        name="buscar_mantenimientos",
        description="Busca el historial de mantenimientos registrados, opcionalmente filtrado por máquina.",
        input_model=MaintenanceSearchParams,
        handler=maintenance_tools.buscar_mantenimientos,
        required_permission=Permission.MAINTENANCE_READ,
        confirmation_level=1,
    ),
    "buscar_mantenimiento_pendiente": ToolDefinition(
        name="buscar_mantenimiento_pendiente",
        description=(
            "Lista las máquinas con mantenimiento preventivo atrasado o próximo a vencer "
            "(por fecha o por horómetro), para responder preguntas como '¿qué máquinas "
            "tienen mantenimiento pendiente?'."
        ),
        input_model=MaintenanceAlertParams,
        handler=maintenance_tools.buscar_mantenimiento_pendiente,
        required_permission=Permission.MAINTENANCE_READ,
        confirmation_level=1,
    ),
    "crear_reunion": ToolDefinition(
        name="crear_reunion",
        description=(
            "Crea una reunión en Google Calendar, verificando disponibilidad de todos los "
            "participantes antes de agendar. Requiere que quien escribe y los participantes "
            "tengan un email configurado. Confirmar antes de agendar si hay más participantes."
        ),
        input_model=CrearReunionInput,
        handler=calendar_tools.crear_reunion,
        required_permission=Permission.CALENDAR_USE,
        confirmation_level=_crear_reunion_confirmation_level,
    ),
    "consultar_calendario": ToolDefinition(
        name="consultar_calendario",
        description="Consulta si quien escribe está disponible en un rango de fecha/hora según su Google Calendar.",
        input_model=ConsultarCalendarioInput,
        handler=calendar_tools.consultar_calendario,
        required_permission=Permission.CALENDAR_USE,
        confirmation_level=1,
    ),
    "preparar_correo": ToolDefinition(
        name="preparar_correo",
        description=(
            "Prepara un borrador de correo (Gmail) con destinatarios, asunto y cuerpo. NO lo "
            "envía — solo lo deja listo. Usa 'enviar_correo' después, con confirmación "
            "explícita del usuario, para enviarlo de verdad."
        ),
        input_model=PrepararCorreoInput,
        handler=email_tools.preparar_correo,
        required_permission=Permission.EMAIL_USE,
        confirmation_level=1,
    ),
    "enviar_correo": ToolDefinition(
        name="enviar_correo",
        description="Envía un borrador de correo previamente preparado con 'preparar_correo'.",
        input_model=EnviarCorreoInput,
        handler=email_tools.enviar_correo,
        required_permission=Permission.EMAIL_USE,
        # Siempre nivel 2: nunca se envía un correo externo sin confirmación explícita
        # (sección 14 del brief), sin excepción — no depende del input.
        confirmation_level=2,
    ),
    "buscar_correos": ToolDefinition(
        name="buscar_correos",
        description="Busca correos en la bandeja de Gmail de quien escribe.",
        input_model=BuscarCorreosInput,
        handler=email_tools.buscar_correos,
        required_permission=Permission.EMAIL_USE,
        confirmation_level=1,
    ),
    "buscar_vehiculo": ToolDefinition(
        name="buscar_vehiculo",
        description="Busca la ficha de un vehículo/camioneta de la flota por patente.",
        input_model=BuscarVehiculoInput,
        handler=vehicle_tools.buscar_vehiculo,
        required_permission=Permission.VEHICLES_READ,
        confirmation_level=1,
    ),
    "consultar_ubicacion_vehiculo": ToolDefinition(
        name="consultar_ubicacion_vehiculo",
        description="Consulta la ubicación actual de un vehículo por GPS (ej. '¿dónde está la camioneta 4?').",
        input_model=ConsultarUbicacionVehiculoInput,
        handler=vehicle_tools.consultar_ubicacion_vehiculo,
        required_permission=Permission.VEHICLES_READ,
        confirmation_level=1,
    ),
    "consultar_kilometraje_vehiculo": ToolDefinition(
        name="consultar_kilometraje_vehiculo",
        description="Consulta los kilómetros recorridos por un vehículo en un rango de fechas (vía GPS).",
        input_model=ConsultarRangoVehiculoInput,
        handler=vehicle_tools.consultar_kilometraje_vehiculo,
        required_permission=Permission.VEHICLES_READ,
        confirmation_level=1,
    ),
    "consultar_viajes_vehiculo": ToolDefinition(
        name="consultar_viajes_vehiculo",
        description="Lista los viajes de un vehículo en un rango de fechas (vía GPS).",
        input_model=ConsultarRangoVehiculoInput,
        handler=vehicle_tools.consultar_viajes_vehiculo,
        required_permission=Permission.VEHICLES_READ,
        confirmation_level=1,
    ),
    "registrar_uso_grua": ToolDefinition(
        name="registrar_uso_grua",
        description="Registra horas de uso de grúa contra el contrato activo de un cliente.",
        input_model=RegistrarUsoGruaInput,
        handler=crane_tools.registrar_uso_grua,
        required_permission=Permission.CRANES_REGISTER,
        confirmation_level=1,
    ),
    "consultar_horas_grua": ToolDefinition(
        name="consultar_horas_grua",
        description=(
            "Consulta horas contratadas/usadas/disponibles de grúa para un cliente. Sin "
            "indicar cliente, lista todos los contratos activos (requiere permiso de gestión)."
        ),
        input_model=ConsultarHorasGruaInput,
        handler=crane_tools.consultar_horas_grua,
        required_permission=Permission.CRANES_READ,
        confirmation_level=1,
    ),
}


def get_tool(name: str) -> ToolDefinition | None:
    return REGISTRY.get(name)


def tools_available_to_role(role: UserRole) -> list[ToolDefinition]:
    return [t for t in REGISTRY.values() if t.required_permission is None or has_permission(role, t.required_permission)]


def llm_schemas_for_role(role: UserRole) -> list[dict[str, Any]]:
    return [t.to_llm_schema() for t in tools_available_to_role(role)]
