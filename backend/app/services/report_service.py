from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.permissions import Permission, has_permission
from app.models.customer import Customer
from app.models.expense import Expense
from app.models.machine import Machine
from app.models.service_order import ServiceOrder
from app.models.user import User
from app.schemas.expense import ExpenseSearchParams
from app.schemas.service_order import ServiceOrderSearchParams
from app.schemas.task import TaskSearchParams
from app.services import expense_service, service_order_service, task_service, user_service

PeriodoLiteral = str  # "dia" | "semana" | "mes" — validado por el schema de la tool


def resolve_periodo(periodo: PeriodoLiteral | None, desde: date | None, hasta: date | None) -> tuple[date | None, date | None]:
    """Traduce un atajo de período ('dia', 'semana', 'mes') a un rango de fechas explícito.
    Si el usuario ya dio ``desde``/``hasta``, esos valores tienen prioridad."""
    if desde is not None or hasta is not None or periodo is None:
        return desde, hasta

    hoy = date.today()
    if periodo == "dia":
        return hoy, hoy
    if periodo == "semana":
        return hoy - timedelta(days=6), hoy
    if periodo == "mes":
        return hoy.replace(day=1), hoy
    return desde, hasta


def _nombre_o_desconocido(nombre: str | None) -> str:
    return nombre or "(sin especificar)"


def generar_reporte_gastos(db: Session, *, actor: User, desde: date | None, hasta: date | None) -> dict:
    params = ExpenseSearchParams(desde=desde, hasta=hasta)
    expenses = expense_service.search_expenses(db, actor=actor, params=params)

    alcance = "empresa completa" if has_permission(actor.rol, Permission.EXPENSES_READ_ALL) else "propio"
    total = sum(float(e.monto) for e in expenses)

    por_trabajador: dict[str, float] = {}
    por_proveedor: dict[str, float] = {}
    por_cliente: dict[str, float] = {}
    por_maquina: dict[str, float] = {}
    por_sucursal: dict[str, float] = {}
    pendientes_de_reembolso = 0.0

    for e in expenses:
        monto = float(e.monto)

        trabajador = db.get(User, e.user_id)
        clave_trabajador = trabajador.nombre_completo if trabajador else "(desconocido)"
        por_trabajador[clave_trabajador] = por_trabajador.get(clave_trabajador, 0.0) + monto
        if trabajador:
            por_sucursal[_nombre_o_desconocido(trabajador.sucursal)] = (
                por_sucursal.get(_nombre_o_desconocido(trabajador.sucursal), 0.0) + monto
            )

        clave_proveedor = _nombre_o_desconocido(e.proveedor)
        por_proveedor[clave_proveedor] = por_proveedor.get(clave_proveedor, 0.0) + monto

        if e.cliente_id:
            cliente = db.get(Customer, e.cliente_id)
            clave_cliente = cliente.nombre if cliente else "(desconocido)"
            por_cliente[clave_cliente] = por_cliente.get(clave_cliente, 0.0) + monto

        if e.maquina_id:
            maquina = db.get(Machine, e.maquina_id)
            clave_maquina = maquina.numero_interno if maquina else "(desconocida)"
            por_maquina[clave_maquina] = por_maquina.get(clave_maquina, 0.0) + monto

        if e.requiere_reembolso and e.estado_reembolso and e.estado_reembolso.value not in ("pagado", "rechazado"):
            pendientes_de_reembolso += monto

    return {
        "alcance": alcance,
        "periodo": {"desde": str(desde) if desde else None, "hasta": str(hasta) if hasta else None},
        "total": total,
        "cantidad_registros": len(expenses),
        "por_categoria": expense_service.total_por_categoria(expenses),
        "por_trabajador": por_trabajador,
        "por_proveedor": por_proveedor,
        "por_cliente": por_cliente,
        "por_maquina": por_maquina,
        "por_sucursal": por_sucursal,
        "pendiente_de_reembolso": pendientes_de_reembolso,
        "registros_usados": [str(e.id) for e in expenses],
    }


def generar_reporte_tareas(
    db: Session, *, actor: User, desde: date | None = None, hasta: date | None = None
) -> dict:
    params = TaskSearchParams()
    tasks = task_service.search_tasks(db, actor=actor, params=params)
    if desde is not None:
        tasks = [t for t in tasks if t.created_at.date() >= desde]
    if hasta is not None:
        tasks = [t for t in tasks if t.created_at.date() <= hasta]

    alcance = "empresa completa" if has_permission(actor.rol, Permission.TASKS_READ_ALL) else "propio"
    por_estado: dict[str, int] = {}
    for t in tasks:
        por_estado[t.estado.value] = por_estado.get(t.estado.value, 0) + 1

    return {
        "alcance": alcance,
        "periodo": {"desde": str(desde) if desde else None, "hasta": str(hasta) if hasta else None},
        "cantidad_registros": len(tasks),
        "completadas": por_estado.get("completada", 0),
        "por_estado": por_estado,
        "registros_usados": [str(t.id) for t in tasks],
    }


def _horas_entre(inicio, fin) -> float | None:
    if inicio is None or fin is None:
        return None
    return (fin - inicio).total_seconds() / 3600


def generar_reporte_servicios(
    db: Session, *, actor: User, desde: date | None = None, hasta: date | None = None
) -> dict:
    params = ServiceOrderSearchParams()
    orders = service_order_service.search_service_orders(db, actor=actor, params=params)
    if desde is not None:
        orders = [o for o in orders if o.fecha >= desde]
    if hasta is not None:
        orders = [o for o in orders if o.fecha <= hasta]

    alcance = "empresa completa" if has_permission(actor.rol, Permission.SERVICES_READ_ALL) else "propio"

    por_tecnico: dict[str, int] = {}
    por_estado: dict[str, int] = {}
    por_cliente: dict[str, int] = {}
    por_maquina: dict[str, int] = {}
    tiempos_atencion: list[float] = []
    tiempos_traslado: list[float] = []

    for o in orders:
        tecnico = user_service.get_by_id(db, o.tecnico_id)
        clave_tecnico = tecnico.nombre_completo if tecnico else "(desconocido)"
        por_tecnico[clave_tecnico] = por_tecnico.get(clave_tecnico, 0) + 1
        por_estado[o.estado.value] = por_estado.get(o.estado.value, 0) + 1

        if o.cliente_id:
            cliente = db.get(Customer, o.cliente_id)
            clave_cliente = cliente.nombre if cliente else "(desconocido)"
            por_cliente[clave_cliente] = por_cliente.get(clave_cliente, 0) + 1

        if o.maquina_id:
            maquina = db.get(Machine, o.maquina_id)
            clave_maquina = maquina.numero_interno if maquina else "(desconocida)"
            por_maquina[clave_maquina] = por_maquina.get(clave_maquina, 0) + 1

        atencion = _horas_entre(o.hora_llegada, o.hora_termino)
        if atencion is not None:
            tiempos_atencion.append(atencion)
        traslado = _horas_entre(o.hora_salida, o.hora_llegada)
        if traslado is not None:
            tiempos_traslado.append(traslado)

    return {
        "alcance": alcance,
        "periodo": {"desde": str(desde) if desde else None, "hasta": str(hasta) if hasta else None},
        "cantidad_registros": len(orders),
        "cerrados": por_estado.get("cerrado", 0),
        "por_tecnico": por_tecnico,
        "por_estado": por_estado,
        "por_cliente": por_cliente,
        "por_maquina": por_maquina,
        "tiempo_promedio_atencion_horas": (
            round(sum(tiempos_atencion) / len(tiempos_atencion), 2) if tiempos_atencion else None
        ),
        "tiempo_promedio_traslado_horas": (
            round(sum(tiempos_traslado) / len(tiempos_traslado), 2) if tiempos_traslado else None
        ),
        "registros_usados": [str(o.id) for o in orders],
    }
