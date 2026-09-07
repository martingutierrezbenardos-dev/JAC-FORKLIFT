from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.permissions import UserRole


class UserBase(BaseModel):
    nombre: str
    apellido: str
    telefono_whatsapp: str = Field(pattern=r"^\+\d{8,15}$")
    email: EmailStr | None = None
    cargo: str = ""
    area: str = ""
    sucursal: str = ""
    rol: UserRole


class UserCreate(UserBase):
    password: str | None = Field(default=None, min_length=8)


class UserUpdate(BaseModel):
    nombre: str | None = None
    apellido: str | None = None
    email: EmailStr | None = None
    cargo: str | None = None
    area: str | None = None
    sucursal: str | None = None
    rol: UserRole | None = None
    activo: bool | None = None


class BuscarUsuarioInput(BaseModel):
    nombre: str | None = Field(default=None, description="Nombre o parte del nombre a buscar.")
    telefono: str | None = Field(default=None, description="Teléfono WhatsApp exacto a buscar.")


class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    activo: bool
    created_at: datetime
