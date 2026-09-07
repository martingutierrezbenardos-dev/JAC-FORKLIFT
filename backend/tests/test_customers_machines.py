from app.core.permissions import UserRole
from app.models.customer import Customer
from app.models.machine import Machine
from app.schemas.customer import BuscarClienteInput
from app.schemas.machine import BuscarMaquinaInput
from app.tools import customer_tools, machine_tools
from app.tools.registry import tools_available_to_role
from tests.conftest import make_user


def test_buscar_cliente_devuelve_ficha(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56977777701")
    db_session.add(Customer(nombre="Cliente Demo", rut="76999999-9", ciudad="Santiago"))
    db_session.flush()

    resultado = customer_tools.buscar_cliente(db_session, tecnico, BuscarClienteInput(nombre="Demo"))

    assert len(resultado["resultados"]) == 1
    assert resultado["resultados"][0]["rut"] == "76999999-9"


def test_buscar_maquina_incluye_nombre_del_cliente(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56977777702")
    cliente = Customer(nombre="Cliente Con Máquina")
    db_session.add(cliente)
    db_session.flush()
    db_session.add(Machine(numero_interno="77", marca="Toyota", estado="operativa", cliente_id=cliente.id))
    db_session.flush()

    resultado = machine_tools.buscar_maquina(db_session, tecnico, BuscarMaquinaInput(numero_interno="77"))

    assert len(resultado["resultados"]) == 1
    assert resultado["resultados"][0]["cliente"] == "Cliente Con Máquina"


def test_gerente_marketing_no_tiene_acceso_a_clientes_ni_maquinas():
    tools = {t.name for t in tools_available_to_role(UserRole.GERENTE_MARKETING)}
    assert "buscar_cliente" not in tools
    assert "buscar_maquina" not in tools


def test_tecnico_si_tiene_acceso_a_clientes_y_maquinas():
    tools = {t.name for t in tools_available_to_role(UserRole.TECNICO)}
    assert "buscar_cliente" in tools
    assert "buscar_maquina" in tools
