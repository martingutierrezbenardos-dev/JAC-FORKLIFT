from __future__ import annotations

from datetime import date, timedelta
from typing import Callable

from sqlalchemy.orm import Session

from app.core.errors import PermissionDeniedError, ValidationDomainError
from app.core.permissions import Permission, has_permission
from app.models.user import User
from app.services import crane_service, maintenance_service, report_service

_TIPOS_VALIDOS = {"gastos", "servicios", "tareas"}

_REPORTES_POR_TIPO: dict[str, Callable[..., dict]] = {
    "gastos": report_service.generar_reporte_gastos,
    "servicios": report_service.generar_reporte_servicios,
    "tareas": report_service.generar_reporte_tareas,
}

# La métrica principal que se compara entre períodos para cada tipo de reporte. El resto de
# cada reporte (desgloses, promedios, etc.) igual queda disponible en detalle_actual/anterior.
_METRICA_PRINCIPAL_POR_TIPO = {
    "gastos": "total",
    "servicios": "cantidad_registros",
    "tareas": "cantidad_registros",
}


def _periodo_por_defecto(periodo: str | None, desde: date | None, hasta: date | None) -> tuple[date, date]:
    desde, hasta = report_service.resolve_periodo(periodo, desde, hasta)
    if desde is None or hasta is None:
        hoy = date.today()
        return hoy.replace(day=1), hoy
    return desde, hasta


def _rango_anterior_equivalente(desde: date, hasta: date) -> tuple[date, date]:
    """Calcula el rango de la misma duración inmediatamente anterior a [desde, hasta], para
    poder comparar 'este mes' contra 'el mes pasado' (o cualquier período contra el anterior
    de igual tamaño) sin que el usuario tenga que especificarlo a mano."""
    dias = (hasta - desde).days + 1
    hasta_anterior = desde - timedelta(days=1)
    desde_anterior = hasta_anterior - timedelta(days=dias - 1)
    return desde_anterior, hasta_anterior


def _variacion(actual: float, anterior: float) -> dict:
    delta = actual - anterior
    porcentaje = round((delta / anterior) * 100, 2) if anterior else None
    return {"absoluta": round(delta, 2), "porcentaje": porcentaje}


def comparar_periodos(
    db: Session,
    *,
    actor: User,
    tipo: str,
    periodo: str | None = "mes",
    desde: date | None = None,
    hasta: date | None = None,
) -> dict:
    """Compara un período contra el período inmediatamente anterior de igual duración, para
    gastos, servicios o tareas. Reusa report_service.generar_reporte_* — los mismos permisos y
    auto-filtrado por usuario que ya aplican a esos reportes aplican aquí (sección 31 del
    brief: nunca se calcula una cifra fuera de los registros que el usuario puede ver)."""
    if tipo not in _TIPOS_VALIDOS:
        raise ValidationDomainError(
            f"Tipo de comparación no soportado: '{tipo}'. Usa 'gastos', 'servicios' o 'tareas'."
        )

    desde, hasta = _periodo_por_defecto(periodo, desde, hasta)
    desde_anterior, hasta_anterior = _rango_anterior_equivalente(desde, hasta)

    generar_reporte = _REPORTES_POR_TIPO[tipo]
    actual = generar_reporte(db, actor=actor, desde=desde, hasta=hasta)
    anterior = generar_reporte(db, actor=actor, desde=desde_anterior, hasta=hasta_anterior)

    metrica = _METRICA_PRINCIPAL_POR_TIPO[tipo]
    return {
        "tipo": tipo,
        "periodo_actual": {"desde": str(desde), "hasta": str(hasta)},
        "periodo_anterior": {"desde": str(desde_anterior), "hasta": str(hasta_anterior)},
        "metrica_comparada": metrica,
        "valor_actual": actual[metrica],
        "valor_anterior": anterior[metrica],
        "variacion": _variacion(actual[metrica], anterior[metrica]),
        "detalle_actual": actual,
        "detalle_anterior": anterior,
    }


def generar_resumen_ejecutivo(
    db: Session,
    *,
    actor: User,
    periodo: str | None = "mes",
    desde: date | None = None,
    hasta: date | None = None,
) -> dict:
    """Resumen ejecutivo cruzando gastos, tareas, servicios, mantenimiento y grúas para un
    período. Requiere REPORTS_VIEW_ALL sin excepción: a diferencia de generar_reporte, que se
    auto-acota a los registros propios cuando falta el permiso 'ALL', un resumen ejecutivo de
    'la empresa' no tiene ninguna versión con sentido acotada a un solo usuario, así que en vez
    de auto-filtrar en silencio se rechaza la operación explicando por qué."""
    if not has_permission(actor.rol, Permission.REPORTS_VIEW_ALL):
        raise PermissionDeniedError(
            "El resumen ejecutivo es información agregada de toda la empresa; "
            "requiere el permiso REPORTS_VIEW_ALL."
        )

    desde, hasta = _periodo_por_defecto(periodo, desde, hasta)
    desde_anterior, hasta_anterior = _rango_anterior_equivalente(desde, hasta)

    gastos_actual = report_service.generar_reporte_gastos(db, actor=actor, desde=desde, hasta=hasta)
    gastos_anterior = report_service.generar_reporte_gastos(
        db, actor=actor, desde=desde_anterior, hasta=hasta_anterior
    )
    tareas_actual = report_service.generar_reporte_tareas(db, actor=actor, desde=desde, hasta=hasta)
    servicios_actual = report_service.generar_reporte_servicios(db, actor=actor, desde=desde, hasta=hasta)
    mantenimiento_pendiente = maintenance_service.get_pending_maintenance_alerts(db, actor=actor)
    contratos_por_agotarse = crane_service.get_contracts_near_limit(db)

    registros_usados = (
        gastos_actual["registros_usados"] + tareas_actual["registros_usados"] + servicios_actual["registros_usados"]
    )

    return {
        "periodo": {"desde": str(desde), "hasta": str(hasta)},
        "periodo_anterior": {"desde": str(desde_anterior), "hasta": str(hasta_anterior)},
        "gastos": {
            "total": gastos_actual["total"],
            "variacion_vs_periodo_anterior": _variacion(gastos_actual["total"], gastos_anterior["total"]),
            "pendiente_de_reembolso": gastos_actual["pendiente_de_reembolso"],
            "por_categoria": gastos_actual["por_categoria"],
        },
        "tareas": {
            "cantidad": tareas_actual["cantidad_registros"],
            "completadas": tareas_actual["completadas"],
            "por_estado": tareas_actual["por_estado"],
        },
        "servicios": {
            "cantidad": servicios_actual["cantidad_registros"],
            "cerrados": servicios_actual["cerrados"],
            "tiempo_promedio_atencion_horas": servicios_actual["tiempo_promedio_atencion_horas"],
        },
        "mantenimiento": {
            "maquinas_con_alerta": len(mantenimiento_pendiente),
            "detalle": mantenimiento_pendiente,
        },
        "gruas": {
            "contratos_por_agotarse": len(contratos_por_agotarse),
            "detalle": contratos_por_agotarse,
        },
        "registros_usados": registros_usados,
    }
