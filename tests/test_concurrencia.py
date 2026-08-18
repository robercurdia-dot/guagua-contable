"""
Concurrencia real: varias emisiones simultaneas contra la MISMA organizacion,
cada una en su propia conexion e hilo.

Es la razon de ser del bloqueo de fila en emision_persistida. Sin el, dos
emisiones leen la misma punta de cadena y producen dos registros que apuntan al
mismo anterior: la cadena se BIFURCA, que es una anomalia de trazabilidad que
el SIF esta obligado a detectar (EventosSIF.xsd, tipos 04-08).

Estos tests no usan la fixture `db` (transaccion unica) a proposito: necesitan
transacciones de verdad, concurrentes y con commit.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.facturacion import LineaCalculo, verificar_libro
from app.servicios import emitir_y_registrar, sesion_tenant
from app.verifactu.huella import EslabonCadena

pytestmark = pytest.mark.postgres

TZ = timezone(timedelta(hours=1))
ORG = "org-concurrencia"


@pytest.fixture
def org_limpia(engine):
    """Organizacion recien creada y vaciada al terminar."""
    with engine.begin() as c:
        c.execute(text("SELECT set_config('app.organizacion_id', :o, true)"), {"o": ORG})
        c.execute(text("INSERT INTO organizacion (id, nif, razon_social) VALUES "
                       "(:o,'B99999999','Concurrencia') ON CONFLICT (id) DO NOTHING"),
                  {"o": ORG})
        c.execute(text("INSERT INTO serie (id, organizacion_id, codigo) VALUES "
                       "('s-conc',:o,'C/2026') ON CONFLICT DO NOTHING"), {"o": ORG})
        c.execute(text("INSERT INTO cliente (id, organizacion_id, nif, nombre) VALUES "
                       "('cli-conc',:o,'A87654321','C') ON CONFLICT DO NOTHING"),
                  {"o": ORG})
    yield
    # limpiar: los registros son append-only, hay que quitar el trigger primero
    with engine.begin() as c:
        c.execute(text("ALTER TABLE registro_facturacion DISABLE TRIGGER "
                       "trg_registro_facturacion_append_only"))
        c.execute(text("SELECT set_config('app.organizacion_id', :o, true)"), {"o": ORG})
        for t in ("registro_facturacion", "linea_factura", "factura", "serie", "cliente"):
            c.execute(text(f"DELETE FROM {t} WHERE organizacion_id = :o"), {"o": ORG})
        c.execute(text("ALTER TABLE registro_facturacion ENABLE TRIGGER "
                       "trg_registro_facturacion_append_only"))
        c.execute(text("DELETE FROM organizacion WHERE id = :o"), {"o": ORG})


def emitir_una(engine, i):
    with sesion_tenant(engine, ORG) as s:
        return emitir_y_registrar(
            s, organizacion_id=ORG, serie_codigo="C/2026", cliente_id="cli-conc",
            lineas=[LineaCalculo("Servicio", Decimal("1"), Decimal("100"))],
            fecha_expedicion=date(2026, 1, 15),
            generado_en=datetime(2026, 1, 15, 10, 0, i % 60, tzinfo=TZ),
        )


def test_emisiones_concurrentes_no_bifurcan_la_cadena(engine, org_limpia):
    """20 emisiones a la vez sobre la misma organizacion."""
    N = 20
    with ThreadPoolExecutor(max_workers=N) as pool:
        resultados = list(pool.map(lambda i: emitir_una(engine, i), range(N)))

    # 1. numeracion correlativa sin huecos ni repetidos
    assert sorted(r.numero for r in resultados) == list(range(1, N + 1))

    # 2. todas las huellas distintas
    assert len({r.huella for r in resultados}) == N

    # 3. la cadena es LINEAL: cada huella_anterior se usa una sola vez
    anteriores = [r.huella_anterior for r in resultados]
    assert len(set(anteriores)) == N, "hay huellas anteriores repetidas -> cadena bifurcada"

    # 4. y reconstruida en orden, es integra
    por_anterior = {r.huella_anterior: r for r in resultados}
    cadena, actual = [], ""
    while actual in por_anterior:
        r = por_anterior[actual]
        cadena.append(EslabonCadena(huella=r.huella, huella_anterior=r.huella_anterior))
        actual = r.huella
    assert len(cadena) == N, f"la cadena solo enlaza {len(cadena)} de {N} registros"
    assert verificar_libro(cadena) is True


def test_la_punta_final_coincide_con_el_ultimo_registro(engine, org_limpia):
    N = 10
    with ThreadPoolExecutor(max_workers=N) as pool:
        resultados = list(pool.map(lambda i: emitir_una(engine, i), range(N)))

    with engine.connect() as c:
        punta = c.execute(text("SELECT cadena_huella FROM organizacion WHERE id=:o"),
                          {"o": ORG}).scalar()
    huellas = {r.huella for r in resultados}
    anteriores = {r.huella_anterior for r in resultados}
    # la punta es la unica huella que nadie referencia como anterior
    assert punta in huellas
    assert (huellas - anteriores) == {punta}


def test_numeracion_sin_duplicados_en_base(engine, org_limpia):
    N = 15
    with ThreadPoolExecutor(max_workers=N) as pool:
        list(pool.map(lambda i: emitir_una(engine, i), range(N)))
    with engine.connect() as c:
        c.execute(text("SELECT set_config('app.organizacion_id', :o, true)"), {"o": ORG})
        total, distintos = c.execute(text(
            "SELECT count(*), count(DISTINCT numero) FROM factura "
            "WHERE organizacion_id = :o"), {"o": ORG}).one()
    assert total == distintos == N
