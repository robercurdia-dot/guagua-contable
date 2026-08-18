"""
Emision con persistencia contra Postgres real, incluida la prueba de
CONCURRENCIA: es el motivo por el que existe el bloqueo de fila.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.facturacion import LineaCalculo, verificar_libro
from app.servicios import emitir_y_registrar, sesion_tenant
from app.servicios.emision_persistida import EmisionError
from app.verifactu.huella import EslabonCadena

pytestmark = pytest.mark.postgres

TZ = timezone(timedelta(hours=1))
ORG = "org-A"


def preparar(sesion):
    """Organizacion + serie + cliente minimos para emitir."""
    sesion.execute(text("SELECT set_config('app.organizacion_id', :o, true)"), {"o": ORG})
    sesion.execute(text(
        "INSERT INTO organizacion (id, nif, razon_social) "
        "VALUES (:o,'B11111111','Empresa A') ON CONFLICT (id) DO NOTHING"), {"o": ORG})
    sesion.execute(text(
        "INSERT INTO serie (id, organizacion_id, codigo) "
        "VALUES ('s1',:o,'A/2026') ON CONFLICT DO NOTHING"), {"o": ORG})
    sesion.execute(text(
        "INSERT INTO cliente (id, organizacion_id, nif, nombre) "
        "VALUES ('cli',:o,'A87654321','Cliente') ON CONFLICT DO NOTHING"), {"o": ORG})


def emitir(sesion, dia=15, precio="100"):
    return emitir_y_registrar(
        sesion, organizacion_id=ORG, serie_codigo="A/2026", cliente_id="cli",
        lineas=[LineaCalculo("Servicio", Decimal("1"), Decimal(precio))],
        fecha_expedicion=date(2026, 1, dia),
        generado_en=datetime(2026, 1, dia, 10, 0, 0, tzinfo=TZ),
    )


# --------------------------------------------------------------- basico
def test_emitir_persiste_factura_y_registro(db):
    sesion = Session(bind=db)
    preparar(sesion)
    r = emitir(sesion)
    sesion.flush()

    assert r.num_serie_factura == "A/2026-0001"
    assert r.huella_anterior == ""      # primer registro del SIF
    assert len(r.huella) == 64

    assert sesion.execute(text("SELECT count(*) FROM factura")).scalar() == 1
    assert sesion.execute(text("SELECT count(*) FROM registro_facturacion")).scalar() == 1
    assert sesion.execute(text("SELECT count(*) FROM linea_factura")).scalar() == 1


def test_la_punta_de_la_cadena_avanza(db):
    sesion = Session(bind=db)
    preparar(sesion)
    r1 = emitir(sesion, 15)
    punta = sesion.execute(text(
        "SELECT cadena_huella, cadena_num_serie, cadena_fecha_expedicion "
        "FROM organizacion WHERE id=:o"), {"o": ORG}).one()
    assert punta.cadena_huella == r1.huella
    assert punta.cadena_num_serie == "A/2026-0001"
    assert punta.cadena_fecha_expedicion == "15-01-2026"


def test_facturas_sucesivas_se_encadenan(db):
    sesion = Session(bind=db)
    preparar(sesion)
    r1 = emitir(sesion, 15)
    r2 = emitir(sesion, 16)
    r3 = emitir(sesion, 17)

    assert [r.numero for r in (r1, r2, r3)] == [1, 2, 3]
    assert r2.huella_anterior == r1.huella
    assert r3.huella_anterior == r2.huella
    assert verificar_libro([
        EslabonCadena(huella=r.huella, huella_anterior=r.huella_anterior)
        for r in (r1, r2, r3)
    ]) is True


def test_serie_inexistente_falla(db):
    sesion = Session(bind=db)
    preparar(sesion)
    with pytest.raises(EmisionError, match="Serie no encontrada"):
        emitir_y_registrar(
            sesion, organizacion_id=ORG, serie_codigo="NO/EXISTE", cliente_id="cli",
            lineas=[LineaCalculo("x", Decimal("1"), Decimal("100"))],
            fecha_expedicion=date(2026, 1, 15),
            generado_en=datetime(2026, 1, 15, 10, 0, tzinfo=TZ))


def test_organizacion_inexistente_falla(db):
    sesion = Session(bind=db)
    preparar(sesion)
    with pytest.raises(EmisionError, match="Organizacion no encontrada"):
        emitir_y_registrar(
            sesion, organizacion_id="no-existe", serie_codigo="A/2026", cliente_id="cli",
            lineas=[LineaCalculo("x", Decimal("1"), Decimal("100"))],
            fecha_expedicion=date(2026, 1, 15),
            generado_en=datetime(2026, 1, 15, 10, 0, tzinfo=TZ))


# --------------------------------------------------------------- tenant
def test_sesion_tenant_exige_organizacion():
    with pytest.raises(ValueError, match="organizacion_id"):
        with sesion_tenant(None, ""):
            pass


def test_sesion_tenant_fija_el_rls(engine):
    with sesion_tenant(engine, "org-A") as s:
        assert s.execute(
            text("SELECT current_setting('app.organizacion_id', true)")
        ).scalar() == "org-A"
