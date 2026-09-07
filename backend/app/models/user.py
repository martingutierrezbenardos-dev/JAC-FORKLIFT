from __future__ import annotations

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.permissions import UserRole
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    apellido: Mapped[str] = mapped_column(String(120), nullable=False)
    telefono_whatsapp: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cargo: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    area: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    sucursal: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    rol: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombre} {self.apellido}".strip()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.telefono_whatsapp} ({self.rol.value})>"
