from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import domain_errors_as_http
from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.expense import ExpenseSearchParams
from app.services import analytics_service, export_service, expense_service, maintenance_service, report_service

router = APIRouter(prefix="/api/reports", tags=["reports"])

_EXPORT_CONTENT_TYPES = {
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}


@router.get("/gastos")
def reporte_gastos(
    periodo: str | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    desde, hasta = report_service.resolve_periodo(periodo, desde, hasta)
    return report_service.generar_reporte_gastos(db, actor=current_user, desde=desde, hasta=hasta)


@router.get("/gastos/export")
def exportar_gastos(
    formato: str = "csv",
    periodo: str | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    if formato not in _EXPORT_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Formato no soportado. Usa 'csv', 'xlsx' o 'pdf'.",
        )

    desde, hasta = report_service.resolve_periodo(periodo, desde, hasta)
    expenses = expense_service.search_expenses(
        db, actor=current_user, params=ExpenseSearchParams(desde=desde, hasta=hasta)
    )

    if formato == "csv":
        content = export_service.expenses_to_csv(db, expenses)
    elif formato == "xlsx":
        content = export_service.expenses_to_xlsx(db, expenses)
    else:
        content = export_service.expenses_to_pdf(db, expenses)

    return Response(
        content=content,
        media_type=_EXPORT_CONTENT_TYPES[formato],
        headers={"Content-Disposition": f'attachment; filename="gastos.{formato}"'},
    )


@router.get("/tareas")
def reporte_tareas(
    periodo: str | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    desde, hasta = report_service.resolve_periodo(periodo, desde, hasta)
    return report_service.generar_reporte_tareas(db, actor=current_user, desde=desde, hasta=hasta)


@router.get("/servicios")
def reporte_servicios(
    periodo: str | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    desde, hasta = report_service.resolve_periodo(periodo, desde, hasta)
    return report_service.generar_reporte_servicios(db, actor=current_user, desde=desde, hasta=hasta)


@router.get("/mantenimiento-pendiente")
def reporte_mantenimiento_pendiente(
    dias_anticipacion: int = 7,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    alertas = maintenance_service.get_pending_maintenance_alerts(
        db, actor=current_user, dias_anticipacion=dias_anticipacion
    )
    return {"cantidad": len(alertas), "alertas": alertas}


@router.get("/comparar")
def comparar_periodos(
    tipo: str = "gastos",
    periodo: str | None = "mes",
    desde: date | None = None,
    hasta: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    with domain_errors_as_http():
        return analytics_service.comparar_periodos(
            db, actor=current_user, tipo=tipo, periodo=periodo, desde=desde, hasta=hasta
        )


@router.get("/resumen-ejecutivo")
def resumen_ejecutivo(
    periodo: str | None = "mes",
    desde: date | None = None,
    hasta: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    with domain_errors_as_http():
        return analytics_service.generar_resumen_ejecutivo(
            db, actor=current_user, periodo=periodo, desde=desde, hasta=hasta
        )
