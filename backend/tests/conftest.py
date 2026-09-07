import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://jacobea:jacobea@localhost:5432/jacobea_test")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-used")
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret")
os.environ.setdefault("ENVIRONMENT", "test")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session as SASession

from app.core.config import get_settings
from app.core.permissions import UserRole
from app.core.security import hash_password
from app.db.session import get_db
from app.main import app as fastapi_app
from app.models.user import User

settings = get_settings()
_engine = create_engine(settings.database_url, future=True)


@pytest.fixture()
def db_session():
    """Sesión de base de datos aislada por test: todo lo escrito se revierte al finalizar.

    Usa el patrón oficial de SQLAlchemy para pruebas (transacción externa + savepoints), de
    forma que incluso si el código bajo prueba llama a ``session.commit()`` (como hacen los
    endpoints REST), los cambios no persisten entre tests.
    """
    connection = _engine.connect()
    outer_transaction = connection.begin()
    session = SASession(bind=connection, future=True)

    connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, transaction):
        if transaction.nested and not transaction._parent.nested:
            connection.begin_nested()

    try:
        yield session
    finally:
        session.close()
        outer_transaction.rollback()
        connection.close()


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    with TestClient(fastapi_app) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()


def make_user(
    db_session,
    *,
    rol: UserRole,
    telefono: str,
    nombre: str = "Test",
    apellido: str = "User",
    email: str | None = None,
    password: str | None = None,
    sucursal: str = "Santiago",
) -> User:
    user = User(
        nombre=nombre,
        apellido=apellido,
        telefono_whatsapp=telefono,
        email=email,
        password_hash=hash_password(password) if password else None,
        cargo="Cargo de prueba",
        area="Area de prueba",
        sucursal=sucursal,
        rol=rol,
    )
    db_session.add(user)
    db_session.flush()
    return user
