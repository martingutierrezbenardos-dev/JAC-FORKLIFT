from datetime import date

from app.ai.agent import AgentSession
from app.ai.client import LLMResponse, ToolCallRequest
from app.core.permissions import UserRole
from app.models.expense import PaymentMethod
from app.models.pending_action import PendingActionStatus
from app.models.task import TaskStatus
from app.schemas.expense import ExpenseCreate, ExpenseSearchParams
from app.schemas.task import TaskSearchParams
from app.services import expense_service, task_service
from app.tools.registry import get_tool, tools_available_to_role
from tests.conftest import make_user
from tests.fakes import FakeLLMClient


def test_registry_filters_tools_by_role():
    tecnico_tools = {t.name for t in tools_available_to_role(UserRole.TECNICO)}
    marketing_tools = {t.name for t in tools_available_to_role(UserRole.GERENTE_MARKETING)}

    assert "crear_gasto" in tecnico_tools
    assert "crear_gasto" not in marketing_tools  # marketing no tiene permisos de gastos


def test_crear_gasto_nivel1_se_ejecuta_de_inmediato(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56955555551")

    llm = FakeLLMClient(
        [
            LLMResponse(
                text=None,
                tool_calls=[
                    ToolCallRequest(
                        id="call_1",
                        name="crear_gasto",
                        input={
                            "fecha": str(date.today()),
                            "monto": 85000,
                            "categoria": "repuesto",
                            "proveedor": "Repuestos X",
                            "forma_pago": "efectivo_propio",
                        },
                    )
                ],
            ),
            LLMResponse(text="Listo, registré tu gasto de 85.000 en repuesto."),
        ]
    )
    agent = AgentSession(llm_client=llm)

    reply = agent.handle_message(db_session, tecnico, "Compré un rodamiento en Repuestos X, 85 lucas, plata mía")

    assert "registré" in reply.lower()
    gastos = expense_service.search_expenses(db_session, actor=tecnico, params=ExpenseSearchParams())
    assert len(gastos) == 1
    assert gastos[0].monto == 85000
    assert len(llm.calls) == 2  # una llamada pidió la tool, otra confirmó el resultado


def test_actualizar_gasto_requiere_confirmacion_antes_de_ejecutarse(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56955555552")
    gasto = expense_service.create_expense(
        db_session, actor=tecnico,
        data=ExpenseCreate(fecha=date.today(), monto=50000, categoria="repuesto", forma_pago=PaymentMethod.EFECTIVO_PROPIO),
    )

    llm = FakeLLMClient(
        [LLMResponse(tool_calls=[ToolCallRequest(id="c1", name="actualizar_gasto", input={"monto": 90000})])]
    )
    agent = AgentSession(llm_client=llm)

    reply = agent.handle_message(db_session, tecnico, "cambia el monto de ese gasto a 90 mil")

    assert "confirmas" in reply.lower()
    # el gasto NO debe haberse modificado todavía
    assert expense_service.get_expense(db_session, gasto.id).monto == 50000

    # el usuario confirma en un mensaje siguiente
    llm2 = FakeLLMClient([LLMResponse(text="Listo, actualicé el gasto a 90.000.")])
    agent2 = AgentSession(llm_client=llm2)
    reply2 = agent2.handle_message(db_session, tecnico, "sí")

    assert expense_service.get_expense(db_session, gasto.id).monto == 90000
    assert "actualicé" in reply2.lower() or "listo" in reply2.lower()


def test_cancelar_accion_pendiente(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56955555553")
    gasto = expense_service.create_expense(
        db_session, actor=tecnico,
        data=ExpenseCreate(fecha=date.today(), monto=30000, categoria="peaje", forma_pago=PaymentMethod.EFECTIVO_PROPIO),
    )

    llm = FakeLLMClient(
        [LLMResponse(tool_calls=[ToolCallRequest(id="c1", name="actualizar_gasto", input={"monto": 99999})])]
    )
    agent = AgentSession(llm_client=llm)
    agent.handle_message(db_session, tecnico, "cambia el monto a 99999")

    agent2 = AgentSession(llm_client=FakeLLMClient([]))
    reply = agent2.handle_message(db_session, tecnico, "no")

    assert "no hice" in reply.lower()
    assert expense_service.get_expense(db_session, gasto.id).monto == 30000


def test_crear_tarea_asignada_a_otro_requiere_confirmacion_y_permiso(db_session):
    jefe = make_user(db_session, rol=UserRole.JEFE_SERVICIOS_TECNICOS, telefono="+56955555554")
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56955555555", nombre="Tecnico")

    llm = FakeLLMClient(
        [
            LLMResponse(
                tool_calls=[
                    ToolCallRequest(
                        id="c1", name="crear_tarea",
                        input={"titulo": "Revisar máquina 33", "asignado_a_telefono": tecnico.telefono_whatsapp},
                    )
                ]
            )
        ]
    )
    agent = AgentSession(llm_client=llm)
    reply = agent.handle_message(db_session, jefe, "ponle a Tecnico revisar la máquina 33 el viernes")

    assert "confirmas" in reply.lower()
    assert task_service.search_tasks(db_session, actor=jefe, params=TaskSearchParams()) == []

    llm2 = FakeLLMClient([LLMResponse(text="Listo, le asigné la tarea.")])
    agent2 = AgentSession(llm_client=llm2)
    agent2.handle_message(db_session, jefe, "dale")

    tareas = task_service.search_tasks(db_session, actor=jefe, params=TaskSearchParams())
    assert len(tareas) == 1
    assert tareas[0].asignado_a == tecnico.id
    assert tareas[0].estado == TaskStatus.PENDIENTE


def test_tool_call_a_herramienta_desconocida_no_rompe_el_loop(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56955555556")
    llm = FakeLLMClient(
        [
            LLMResponse(tool_calls=[ToolCallRequest(id="c1", name="tool_que_no_existe", input={})]),
            LLMResponse(text="No pude hacer eso."),
        ]
    )
    agent = AgentSession(llm_client=llm)
    reply = agent.handle_message(db_session, tecnico, "haz algo raro")
    assert reply == "No pude hacer eso."


def test_dispatch_rechaza_tool_sin_permiso(db_session):
    marketing = make_user(db_session, rol=UserRole.GERENTE_MARKETING, telefono="+56955555557")
    llm = FakeLLMClient(
        [
            LLMResponse(
                tool_calls=[
                    ToolCallRequest(
                        id="c1", name="crear_gasto",
                        input={
                            "fecha": str(date.today()), "monto": 1000, "categoria": "otros",
                            "forma_pago": "tarjeta_empresa",
                        },
                    )
                ]
            ),
            LLMResponse(text="No tienes permiso para eso."),
        ]
    )
    agent = AgentSession(llm_client=llm)
    agent.handle_message(db_session, marketing, "registra un gasto de 1000")

    # No se creó ningún gasto porque gerente_marketing no tiene permiso.
    assert get_tool("crear_gasto") is not None
    gastos = expense_service.search_expenses(db_session, actor=marketing, params=ExpenseSearchParams())
    assert gastos == []
