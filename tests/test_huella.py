"""
Tests del motor de huella (hash chain) — GATE de la Fase 0.

Estado de los tests:
  - Regresion determinista: CLAVADO (protege contra cambios accidentales del
    algoritmo). Es un hash calculado por nosotros, no un vector oficial.
  - Encadenamiento: verificado.
  - Vector oficial AEAT: ver tests/test_huella_vectores_aeat.py (SUPERADO).
"""
import pytest

from app.verifactu import (
    HUELLA_INICIAL,
    huella_registro_alta,
    huella_registro_anulacion,
    verificar_cadena,
)
from app.verifactu.huella import EslabonCadena

ALTA_EJEMPLO = dict(
    id_emisor="B12345678",
    num_serie_factura="A/2026-0001",
    fecha_expedicion="15-01-2026",
    tipo_factura="F1",
    cuota_total="21.00",
    importe_total="121.00",
    fecha_hora_huso="2026-01-15T10:30:00+01:00",
)

# Hash calculado por nosotros para el ejemplo de arriba (regresion, no oficial).
HUELLA_REGRESION = "49620C925375DFA3B6608B478568696B56F190091CC3021BFD0C1590F1C02B3B"


def test_huella_alta_es_determinista_y_regresion():
    h1 = huella_registro_alta(**ALTA_EJEMPLO)
    h2 = huella_registro_alta(**ALTA_EJEMPLO)
    assert h1 == h2, "la huella debe ser determinista"
    assert h1 == HUELLA_REGRESION, "cambio inesperado en el algoritmo de huella"
    assert len(h1) == 64 and h1 == h1.upper(), "SHA-256 hex en mayusculas"


def test_huella_cambia_si_cambia_un_campo():
    base = huella_registro_alta(**ALTA_EJEMPLO)
    modificado = dict(ALTA_EJEMPLO, importe_total="121.01")
    assert huella_registro_alta(**modificado) != base


def test_encadenamiento_liga_registros():
    h1 = huella_registro_alta(**ALTA_EJEMPLO)
    segundo = dict(ALTA_EJEMPLO, num_serie_factura="A/2026-0002")
    h2 = huella_registro_alta(**segundo, huella_anterior=h1)
    # el segundo registro incorpora la huella del primero -> distinto a sin cadena
    assert h2 != huella_registro_alta(**segundo)


def test_verificar_cadena_ok_y_ko():
    h1 = huella_registro_alta(**ALTA_EJEMPLO)
    h2 = huella_registro_alta(
        **dict(ALTA_EJEMPLO, num_serie_factura="A/2026-0002"), huella_anterior=h1
    )
    buena = [
        EslabonCadena(huella=h1, huella_anterior=HUELLA_INICIAL),
        EslabonCadena(huella=h2, huella_anterior=h1),
    ]
    assert verificar_cadena(buena) is True

    rota = [
        EslabonCadena(huella=h1, huella_anterior=HUELLA_INICIAL),
        EslabonCadena(huella=h2, huella_anterior="0000"),  # no liga
    ]
    assert verificar_cadena(rota) is False


def test_falta_campo_lanza_error():
    with pytest.raises(TypeError):
        huella_registro_alta(id_emisor="B12345678")  # faltan campos


def test_anulacion_determinista():
    h = huella_registro_anulacion(
        id_emisor="B12345678",
        num_serie_factura="A/2026-0001",
        fecha_expedicion="15-01-2026",
        fecha_hora_huso="2026-01-15T11:00:00+01:00",
    )
    assert len(h) == 64 and h == h.upper()
