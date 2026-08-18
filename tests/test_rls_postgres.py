"""
Verificacion del aislamiento multi-tenant (RLS) y de la inalterabilidad
(append-only) CONTRA UN POSTGRES REAL.

Estas garantias no se pueden comprobar con SQLite ni en memoria: son politicas
y triggers del propio motor. Si estos tests no corren, el aislamiento entre
clientes esta sin verificar.
"""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError

pytestmark = pytest.mark.postgres


def tenant(db, org):
    db.execute(text(f"SET LOCAL app.organizacion_id = '{org}'"))


def crear_cliente(db, cid, org, nombre):
    db.execute(
        text("INSERT INTO cliente (id, organizacion_id, nif, nombre) "
             "VALUES (:i,:o,'X',:n)"),
        {"i": cid, "o": org, "n": nombre},
    )


# ------------------------------------------------- aislamiento entre tenants
def test_cada_tenant_solo_ve_lo_suyo(db):
    tenant(db, "org-A")
    crear_cliente(db, "c1", "org-A", "Cliente de A")
    tenant(db, "org-B")
    crear_cliente(db, "c2", "org-B", "Cliente de B")

    tenant(db, "org-A")
    assert db.execute(text("SELECT count(*) FROM cliente")).scalar() == 1
    assert db.execute(text("SELECT nombre FROM cliente")).scalar() == "Cliente de A"

    tenant(db, "org-B")
    assert db.execute(text("SELECT nombre FROM cliente")).scalar() == "Cliente de B"


def test_no_se_puede_insertar_en_otro_tenant(db):
    """La clausula WITH CHECK impide colar filas en otra organizacion."""
    tenant(db, "org-A")
    with pytest.raises(DatabaseError, match="row-level security"):
        crear_cliente(db, "c3", "org-B", "Infiltrado")


def test_no_se_puede_borrar_de_otro_tenant(db):
    tenant(db, "org-B")
    crear_cliente(db, "c4", "org-B", "De B")
    tenant(db, "org-A")
    r = db.execute(text("DELETE FROM cliente WHERE id='c4'"))
    assert r.rowcount == 0, "A no deberia poder borrar filas de B"
    tenant(db, "org-B")
    assert db.execute(text("SELECT count(*) FROM cliente WHERE id='c4'")).scalar() == 1


def test_sin_tenant_no_se_ve_nada(db):
    """
    PROPIEDAD DE SEGURIDAD: si la app olvida fijar el tenant, la consulta no
    devuelve nada en lugar de devolverlo todo. Falla en cerrado.
    """
    tenant(db, "org-A")
    crear_cliente(db, "c5", "org-A", "De A")
    db.execute(text("RESET app.organizacion_id"))
    assert db.execute(text("SELECT count(*) FROM cliente")).scalar() == 0
    assert db.execute(text("SELECT count(*) FROM registro_facturacion")).scalar() == 0


@pytest.mark.parametrize("tabla", [
    "serie", "cliente", "producto", "factura", "linea_factura",
    "registro_facturacion", "evento_sif",
])
def test_todas_las_tablas_de_negocio_tienen_rls_forzado(db, tabla):
    """
    FORCE ROW LEVEL SECURITY es imprescindible: sin el, el DUENO de la tabla
    (que es el usuario con el que se conecta la app) se salta las politicas.
    """
    fila = db.execute(
        text("SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
             "WHERE relname = :t"), {"t": tabla}
    ).one()
    assert fila.relrowsecurity, f"{tabla}: RLS no habilitado"
    assert fila.relforcerowsecurity, f"{tabla}: RLS no forzado sobre el dueno"


# ------------------------------------------------- inalterabilidad
def crear_registro(db, rid="r1"):
    db.execute(
        text("INSERT INTO registro_facturacion "
             "(id, organizacion_id, tipo, factura_id, huella, huella_anterior, "
             " fecha_hora_huso) VALUES "
             "(:i,'org-A','alta','f1','HUELLA_ORIGINAL','','2026-01-15T10:30:00+01:00')"),
        {"i": rid},
    )


def test_no_se_puede_borrar_un_registro_de_facturacion(db):
    tenant(db, "org-A")
    crear_registro(db)
    with pytest.raises(DatabaseError, match="append-only"):
        db.execute(text("DELETE FROM registro_facturacion WHERE id='r1'"))


@pytest.mark.parametrize("campo,valor", [
    ("huella", "'FALSIFICADA'"),
    ("huella_anterior", "'OTRA'"),
    ("factura_id", "'f99'"),
    ("tipo", "'anulacion'"),
    ("fecha_hora_huso", "'2020-01-01T00:00:00+01:00'"),
    ("xml", "'<falso/>'"),
])
def test_los_campos_que_forman_la_prueba_son_inalterables(db, campo, valor):
    tenant(db, "org-A")
    crear_registro(db)
    with pytest.raises(DatabaseError, match="inalterable"):
        db.execute(text(f"UPDATE registro_facturacion SET {campo}={valor} WHERE id='r1'"))


def test_si_se_puede_anotar_la_respuesta_de_la_aeat(db):
    """
    Excepcion controlada: el resultado del envio SI debe poder anotarse, porque
    llega despues de crear el registro. La huella no se toca.
    """
    tenant(db, "org-A")
    crear_registro(db)
    db.execute(text(
        "UPDATE registro_facturacion SET estado_aeat='aceptado', "
        "respuesta_aeat='{\"csv\":\"ABC\"}' WHERE id='r1'"))
    fila = db.execute(text(
        "SELECT huella, estado_aeat FROM registro_facturacion WHERE id='r1'")).one()
    assert fila.huella == "HUELLA_ORIGINAL"
    assert fila.estado_aeat == "aceptado"


def test_evento_sif_es_completamente_inmutable(db):
    tenant(db, "org-A")
    db.execute(text(
        "INSERT INTO evento_sif (id, organizacion_id, tipo_evento, ocurrido_en) "
        "VALUES ('e1','org-A','01', now())"))
    with pytest.raises(DatabaseError, match="append-only"):
        db.execute(text("UPDATE evento_sif SET tipo_evento='02' WHERE id='e1'"))


# ------------------------------------------------- constraints legales
def test_numeracion_no_admite_duplicados_en_la_serie(db):
    """Requisito legal: la numeracion dentro de una serie es unica."""
    tenant(db, "org-A")
    db.execute(text("INSERT INTO serie (id, organizacion_id, codigo) "
                    "VALUES ('s1','org-A','A/2026')"))
    db.execute(text("INSERT INTO cliente (id, organizacion_id, nif, nombre) "
                    "VALUES ('cli','org-A','X','C')"))
    ins = ("INSERT INTO factura (id, organizacion_id, serie_id, numero, "
           "fecha_expedicion, cliente_id) VALUES "
           "(:i,'org-A','s1',1,'2026-01-15','cli')")
    db.execute(text(ins), {"i": "f1"})
    with pytest.raises(DatabaseError, match="uq_factura_org_serie_numero"):
        db.execute(text(ins), {"i": "f2"})


def test_estado_aeat_solo_admite_valores_validos(db):
    tenant(db, "org-A")
    crear_registro(db)
    with pytest.raises(DatabaseError, match="ck_registro_estado_aeat"):
        db.execute(text("UPDATE registro_facturacion SET estado_aeat='inventado' "
                        "WHERE id='r1'"))
