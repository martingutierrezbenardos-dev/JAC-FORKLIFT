from datetime import date, timedelta

import pytest

from app.core.errors import PermissionDeniedError, ValidationDomainError
from app.core.permissions import UserRole
from app.models.crane import CraneContract, CraneUsage
from app.models.customer import Customer
from app.schemas.crane import CraneContractCreate
from app.services import crane_service
from tests.conftest import make_user


def _create_contract(db_session, cliente, horas_contratadas=100):
    contrato = CraneContract(
        cliente_id=cliente.id, periodo_inicio=date.today(), periodo_fin=date.today() + timedelta(days=30),
        horas_contratadas=horas_contratadas, costo_hora=45000,
    )
    db_session.add(contrato)
    db_session.flush()
    return contrato


def test_registrar_uso_grua_acumula_horas(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56900777001")
    cliente = Customer(nombre="Cliente Grúa")
    db_session.add(cliente)
    db_session.flush()
    _create_contract(db_session, cliente)

    resultado = crane_service.registrar_uso_grua(
        db_session, actor=tecnico, cliente_nombre="Cliente Grúa", horas_usadas=10
    )
    resultado2 = crane_service.registrar_uso_grua(
        db_session, actor=tecnico, cliente_nombre="Cliente Grúa", horas_usadas=5
    )

    assert resultado2["contrato"]["horas_utilizadas"] == 15.0
    assert resultado2["contrato"]["horas_disponibles"] == 85.0


def test_registrar_uso_grua_sin_contrato_activo_falla(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56900777002")
    db_session.add(Customer(nombre="Cliente Sin Contrato"))
    db_session.flush()

    with pytest.raises(ValidationDomainError):
        crane_service.registrar_uso_grua(
            db_session, actor=tecnico, cliente_nombre="Cliente Sin Contrato", horas_usadas=5
        )


def test_consultar_horas_grua_por_cliente(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56900777003")
    cliente = Customer(nombre="Cliente Consulta")
    db_session.add(cliente)
    db_session.flush()
    contrato = _create_contract(db_session, cliente, horas_contratadas=100)
    db_session.add(CraneUsage(contrato_id=contrato.id, registrado_por=tecnico.id, fecha=date.today(), horas_usadas=90))
    db_session.flush()

    resultado = crane_service.consultar_horas_grua(db_session, actor=tecnico, cliente_nombre="Cliente Consulta")

    assert len(resultado["contratos"]) == 1
    assert resultado["contratos"][0]["porcentaje_usado"] == 90.0
    assert resultado["contratos"][0]["alerta"] is True


def test_consultar_horas_grua_sin_cliente_requiere_permiso_de_gestion(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56900777004")

    with pytest.raises(PermissionDeniedError):
        crane_service.consultar_horas_grua(db_session, actor=tecnico, cliente_nombre=None)


def test_administracion_puede_listar_todos_los_contratos(db_session):
    admin = make_user(db_session, rol=UserRole.ADMINISTRACION, telefono="+56900777005")
    cliente = Customer(nombre="Cliente Listado")
    db_session.add(cliente)
    db_session.flush()
    _create_contract(db_session, cliente)

    resultado = crane_service.consultar_horas_grua(db_session, actor=admin, cliente_nombre=None)

    assert len(resultado["contratos"]) >= 1


def test_crear_contrato_requiere_permiso_de_gestion(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56900777006")
    db_session.add(Customer(nombre="Cliente Nuevo"))
    db_session.flush()

    with pytest.raises(PermissionDeniedError):
        crane_service.create_crane_contract(
            db_session, actor=tecnico,
            data=CraneContractCreate(
                cliente_nombre="Cliente Nuevo", periodo_inicio=date.today(),
                periodo_fin=date.today() + timedelta(days=30), horas_contratadas=50, costo_hora=40000,
            ),
        )


def test_administracion_puede_crear_contrato(db_session):
    admin = make_user(db_session, rol=UserRole.ADMINISTRACION, telefono="+56900777007")
    db_session.add(Customer(nombre="Cliente Contrato Nuevo"))
    db_session.flush()

    resultado = crane_service.create_crane_contract(
        db_session, actor=admin,
        data=CraneContractCreate(
            cliente_nombre="Cliente Contrato Nuevo", periodo_inicio=date.today(),
            periodo_fin=date.today() + timedelta(days=30), horas_contratadas=50, costo_hora=40000,
        ),
    )

    assert resultado["cliente"] == "Cliente Contrato Nuevo"
    assert resultado["horas_contratadas"] == 50.0
