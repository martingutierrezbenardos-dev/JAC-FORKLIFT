from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.expense import Currency


class RegistrarUsoGruaInput(BaseModel):
    cliente_nombre: str
    horas_usadas: Decimal = Field(gt=0)
    fecha: date | None = None
    observaciones: str | None = None


class ConsultarHorasGruaInput(BaseModel):
    cliente_nombre: str | None = Field(
        default=None,
        description="Nombre del cliente. Si se omite, se listan todos los contratos activos (requiere permiso de gestión).",
    )


class CraneContractCreate(BaseModel):
    """Usado por el endpoint REST (panel web / administración) para crear un contrato —
    no es una tool de IA: crear un contrato es una decisión comercial/contable, no un
    reporte de campo."""

    cliente_nombre: str
    periodo_inicio: date
    periodo_fin: date
    horas_contratadas: Decimal = Field(gt=0)
    costo_hora: Decimal = Field(gt=0)
    moneda: Currency = Currency.CLP
    observaciones: str | None = None
