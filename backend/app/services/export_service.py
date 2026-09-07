"""Exportación de reportes a CSV, Excel y PDF (sección 6 del brief).

Genera los archivos a partir de los mismos registros que ya pasaron por el filtrado de
permisos de ``expense_service.search_expenses`` — nunca vuelve a consultar la base de datos
sin ese filtro.
"""
from __future__ import annotations

import csv
import io

from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.expense import Expense
from app.models.machine import Machine
from app.models.user import User

_HEADERS = [
    "Fecha", "Trabajador", "Categoría", "Monto", "Moneda", "Proveedor",
    "Cliente", "Máquina", "Forma de pago", "Estado de reembolso", "Descripción",
]


def _row_for_expense(db: Session, e: Expense) -> list[str]:
    trabajador = db.get(User, e.user_id)
    cliente = db.get(Customer, e.cliente_id) if e.cliente_id else None
    maquina = db.get(Machine, e.maquina_id) if e.maquina_id else None
    return [
        str(e.fecha),
        trabajador.nombre_completo if trabajador else "",
        e.categoria.value,
        str(e.monto),
        e.moneda.value,
        e.proveedor or "",
        cliente.nombre if cliente else "",
        maquina.numero_interno if maquina else "",
        e.forma_pago.value,
        e.estado_reembolso.value if e.estado_reembolso else "",
        e.descripcion or "",
    ]


def expenses_to_csv(db: Session, expenses: list[Expense]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_HEADERS)
    for e in expenses:
        writer.writerow(_row_for_expense(db, e))
    # utf-8-sig (con BOM) para que Excel abra los acentos correctamente en Windows.
    return buffer.getvalue().encode("utf-8-sig")


def expenses_to_xlsx(db: Session, expenses: list[Expense]) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Gastos"
    ws.append(_HEADERS)
    for e in expenses:
        ws.append(_row_for_expense(db, e))

    for column_cells in ws.columns:
        length = max((len(str(cell.value)) for cell in column_cells if cell.value is not None), default=0)
        ws.column_dimensions[column_cells[0].column_letter].width = min(max(length + 2, 10), 40)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def expenses_to_pdf(db: Session, expenses: list[Expense], *, titulo: str = "Reporte de gastos") -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    styles = getSampleStyleSheet()
    elements = [Paragraph(titulo, styles["Title"]), Spacer(1, 12)]

    data = [_HEADERS] + [_row_for_expense(db, e) for e in expenses]
    table = Table(data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
            ]
        )
    )
    elements.append(table)

    total = sum(float(e.monto) for e in expenses)
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Total: {total:,.0f}", styles["Normal"]))

    doc.build(elements)
    return buffer.getvalue()
