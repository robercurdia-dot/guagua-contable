import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

# Base de datos de pruebas. Los tests que la usan se saltan si no hay Postgres
# a mano, para que la suite siga corriendo en una maquina sin base de datos.
URL_TEST = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://guagua:guagua@localhost:5432/guagua_test",
)


def _hay_postgres() -> bool:
    try:
        from sqlalchemy import create_engine, text

        with create_engine(URL_TEST).connect() as c:
            c.execute(text("select 1"))
        return True
    except Exception:
        return False


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "postgres: necesita un Postgres real (aislamiento RLS y triggers)"
    )


def pytest_collection_modifyitems(config, items):
    """Se saltan los tests de Postgres si no hay base a mano."""
    if _hay_postgres():
        return
    saltar = pytest.mark.skip(reason="sin Postgres en TEST_DATABASE_URL")
    for item in items:
        if "postgres" in item.keywords:
            item.add_marker(saltar)


@pytest.fixture(scope="session")
def engine():
    """Motor contra la base de pruebas, con el esquema ya migrado."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine

    os.environ["DATABASE_URL"] = URL_TEST
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", URL_TEST)
    command.upgrade(cfg, "head")
    eng = create_engine(URL_TEST)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine):
    """
    Conexion limpia por test: cada test corre en una transaccion que se
    deshace al terminar, para que no se contaminen entre si.
    """
    from sqlalchemy import text

    conn = engine.connect()
    trans = conn.begin()
    # datos base: dos organizaciones para probar el aislamiento
    conn.execute(text("SET LOCAL app.organizacion_id = 'org-A'"))
    for oid, nif, nombre in (("org-A", "B11111111", "Empresa A"),
                             ("org-B", "B22222222", "Empresa B")):
        conn.execute(
            text("INSERT INTO organizacion (id, nif, razon_social) "
                 "VALUES (:i,:n,:r) ON CONFLICT (id) DO NOTHING"),
            {"i": oid, "n": nif, "r": nombre},
        )
    yield conn
    trans.rollback()
    conn.close()
