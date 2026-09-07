from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationDomainError
from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


def get_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def get_by_phone(db: Session, telefono_whatsapp: str) -> User | None:
    stmt = select(User).where(User.telefono_whatsapp == telefono_whatsapp)
    return db.execute(stmt).scalar_one_or_none()


def get_by_email(db: Session, email: str) -> User | None:
    stmt = select(User).where(User.email == email)
    return db.execute(stmt).scalar_one_or_none()


def search_by_name(db: Session, nombre: str, limit: int = 5) -> list[User]:
    stmt = (
        select(User)
        .where(User.activo.is_(True))
        .where((User.nombre + " " + User.apellido).ilike(f"%{nombre}%"))
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def list_all(db: Session) -> list[User]:
    stmt = select(User).order_by(User.nombre, User.apellido)
    return list(db.execute(stmt).scalars().all())


def create_user(db: Session, data: UserCreate) -> User:
    if get_by_phone(db, data.telefono_whatsapp) is not None:
        raise ValidationDomainError("Ya existe un usuario con ese teléfono de WhatsApp.")
    if data.email and get_by_email(db, data.email) is not None:
        raise ValidationDomainError("Ya existe un usuario con ese email.")

    user = User(
        nombre=data.nombre,
        apellido=data.apellido,
        telefono_whatsapp=data.telefono_whatsapp,
        email=data.email,
        cargo=data.cargo,
        area=data.area,
        sucursal=data.sucursal,
        rol=data.rol,
        password_hash=hash_password(data.password) if data.password else None,
    )
    db.add(user)
    db.flush()
    return user


def update_user(db: Session, user_id: uuid.UUID, data: UserUpdate) -> User:
    user = get_by_id(db, user_id)
    if user is None:
        raise NotFoundError("Usuario no encontrado.")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.flush()
    return user
