import pytest

from app.core.errors import PermissionDeniedError
from app.core.permissions import UserRole
from app.models.task import TaskStatus
from app.schemas.task import TaskCreate, TaskSearchParams
from app.services import task_service
from tests.conftest import make_user


def test_crear_tarea_para_si_mismo(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56944444441")

    tarea = task_service.create_task(db_session, actor=tecnico, data=TaskCreate(titulo="Revisar máquina 33"))

    assert tarea.asignado_a == tecnico.id
    assert tarea.creado_por == tecnico.id
    assert tarea.estado == TaskStatus.PENDIENTE


def test_tecnico_no_puede_asignar_tarea_a_otro(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56944444442")
    otro = make_user(db_session, rol=UserRole.TECNICO, telefono="+56944444443", nombre="Otro")

    with pytest.raises(PermissionDeniedError):
        task_service.create_task(
            db_session, actor=tecnico,
            data=TaskCreate(titulo="Comprar alternador", asignado_a_telefono=otro.telefono_whatsapp),
        )


def test_jefe_servicios_puede_asignar_tarea_a_tecnico(db_session):
    jefe = make_user(db_session, rol=UserRole.JEFE_SERVICIOS_TECNICOS, telefono="+56944444444")
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56944444445", nombre="Tecnico3")

    tarea = task_service.create_task(
        db_session, actor=jefe,
        data=TaskCreate(titulo="Revisar máquina 33 el viernes", asignado_a_telefono=tecnico.telefono_whatsapp),
    )

    assert tarea.asignado_a == tecnico.id
    assert tarea.creado_por == jefe.id


def test_completar_tarea_propia(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56944444446")
    tarea = task_service.create_task(db_session, actor=tecnico, data=TaskCreate(titulo="Comprar alternador"))

    completada = task_service.complete_task(db_session, actor=tecnico, task_id=tarea.id)

    assert completada.estado == TaskStatus.COMPLETADA


def test_no_puede_completar_tarea_ajena_sin_permiso(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56944444447")
    otro = make_user(db_session, rol=UserRole.TECNICO, telefono="+56944444448", nombre="Otro2")
    tarea = task_service.create_task(db_session, actor=otro, data=TaskCreate(titulo="Tarea de otro"))

    with pytest.raises(PermissionDeniedError):
        task_service.complete_task(db_session, actor=tecnico, task_id=tarea.id)


def test_buscar_tareas_por_estado(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56944444449")
    t1 = task_service.create_task(db_session, actor=tecnico, data=TaskCreate(titulo="Tarea 1"))
    task_service.create_task(db_session, actor=tecnico, data=TaskCreate(titulo="Tarea 2"))
    task_service.complete_task(db_session, actor=tecnico, task_id=t1.id)

    pendientes = task_service.search_tasks(
        db_session, actor=tecnico, params=TaskSearchParams(estado=TaskStatus.PENDIENTE)
    )

    assert len(pendientes) == 1
    assert pendientes[0].titulo == "Tarea 2"
