from app.core.config import Settings


def test_database_url_normaliza_esquema_postgres_a_psycopg():
    settings = Settings(database_url="postgres://user:pass@host.railway.internal:5432/railway")

    assert settings.database_url == "postgresql+psycopg://user:pass@host.railway.internal:5432/railway"


def test_database_url_normaliza_esquema_postgresql_a_psycopg():
    settings = Settings(database_url="postgresql://user:pass@host.railway.internal:5432/railway")

    assert settings.database_url == "postgresql+psycopg://user:pass@host.railway.internal:5432/railway"


def test_database_url_con_driver_explicito_no_se_toca():
    url = "postgresql+psycopg://jacobea:jacobea@localhost:5432/jacobea_dev"

    settings = Settings(database_url=url)

    assert settings.database_url == url
