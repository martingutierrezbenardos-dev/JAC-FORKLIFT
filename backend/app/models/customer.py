from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Customer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Ficha mínima de cliente.

    Fase 1 solo la usa como referencia opcional en ``expenses``. El módulo completo de
    clientes (contratos, visitas, órdenes de compra) es Fase 2.
    """

    __tablename__ = "customers"

    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    rut: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    direccion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    comuna: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ciudad: Mapped[str | None] = mapped_column(String(120), nullable=True)
    contacto: Mapped[str | None] = mapped_column(String(120), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tipo_cliente: Mapped[str | None] = mapped_column(String(80), nullable=True)
    estado: Mapped[str] = mapped_column(String(40), nullable=False, default="activo")
