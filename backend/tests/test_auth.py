from app.core.permissions import UserRole
from tests.conftest import make_user


def test_login_success(client, db_session):
    make_user(
        db_session, rol=UserRole.GERENTE_GENERAL, telefono="+56911111111",
        email="gerente@jacobea.cl", password="clave-segura-123",
    )
    db_session.commit()

    response = client.post("/api/auth/login", json={"email": "gerente@jacobea.cl", "password": "clave-segura-123"})

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["user"]["email"] == "gerente@jacobea.cl"


def test_login_wrong_password(client, db_session):
    make_user(
        db_session, rol=UserRole.GERENTE_GENERAL, telefono="+56911111112",
        email="gerente2@jacobea.cl", password="clave-segura-123",
    )
    db_session.commit()

    response = client.post("/api/auth/login", json={"email": "gerente2@jacobea.cl", "password": "otra-clave"})

    assert response.status_code == 401


def test_login_unknown_email(client, db_session):
    response = client.post("/api/auth/login", json={"email": "nadie@jacobea.cl", "password": "x"})
    assert response.status_code == 401


def test_login_inactive_user(client, db_session):
    user = make_user(
        db_session, rol=UserRole.GERENTE_GENERAL, telefono="+56911111113",
        email="inactivo@jacobea.cl", password="clave-segura-123",
    )
    user.activo = False
    db_session.commit()

    response = client.post("/api/auth/login", json={"email": "inactivo@jacobea.cl", "password": "clave-segura-123"})
    assert response.status_code == 401


def test_protected_endpoint_requires_token(client):
    response = client.get("/api/expenses")
    assert response.status_code == 401
