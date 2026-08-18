"""
Test end-to-end del ciclo de facturacion: emitir -> emitir -> anular,
verificando que la cadena Verifactu queda integra.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.facturacion import (
    LineaCalculo,
    anular_factura,
    emitir_factura,
    fecha_aeat,
    fecha_hora_huso,
    verificar_libro,
)
from app.verifactu import HUELLA_INICIAL

MADRID = timezone(timedelta(hours=1))
NIF = "89890001K"


def linea(cantidad, precio, tipo_iva="21"):
    return LineaCalculo(
        descripcion="Servicio",
        cantidad=Decimal(str(cantidad)),
        precio=Decimal(str(precio)),
        tipo_iva=Decimal(str(tipo_iva)),
    )


# ------------------------------------------------------------ formatos AEAT
def test_fecha_formato_aeat():
    assert fecha_aeat(date(2024, 1, 1)) == "01-01-2024"
    assert fecha_aeat(date(2026, 12, 31)) == "31-12-2026"


def test_fecha_hora_huso_exige_tz():
    with pytest.raises(ValueError, match="huso horario"):
        fecha_hora_huso(datetime(2024, 1, 1, 19, 20, 30))  # naive


def test_fecha_hora_huso_formato():
    dt = datetime(2024, 1, 1, 19, 20, 30, tzinfo=MADRID)
    assert fecha_hora_huso(dt) == "2024-01-01T19:20:30+01:00"


# ------------------------------------------------------------ emision
def test_primera_factura_del_sif():
    f = emitir_factura(
        nif_emisor=NIF,
        serie="A/2026",
        ultimo_numero=0,
        lineas=[linea(1, 100)],
        fecha_expedicion=date(2026, 1, 15),
        generado_en=datetime(2026, 1, 15, 10, 30, 0, tzinfo=MADRID),
    )
    assert f.numero == 1
    assert f.num_serie_factura == "A/2026-0001"
    assert f.huella_anterior == HUELLA_INICIAL
    assert len(f.huella) == 64
    assert f.totales.importe_total_str == "121.00"
    assert f.totales.cuota_total_str == "21.00"


def test_numeracion_correlativa_entre_facturas():
    comun = dict(
        nif_emisor=NIF, serie="A/2026", lineas=[linea(1, 100)],
        fecha_expedicion=date(2026, 1, 15),
        generado_en=datetime(2026, 1, 15, 10, 30, tzinfo=MADRID),
    )
    f1 = emitir_factura(ultimo_numero=0, **comun)
    f2 = emitir_factura(ultimo_numero=f1.numero, huella_anterior=f1.huella, **comun)
    assert (f1.numero, f2.numero) == (1, 2)
    assert f2.num_serie_factura == "A/2026-0002"


def test_cadena_de_dos_facturas_y_una_anulacion():
    """Ciclo completo: alta -> alta -> anulacion. La cadena debe ser integra."""
    f1 = emitir_factura(
        nif_emisor=NIF, serie="A/2026", ultimo_numero=0,
        lineas=[linea(1, 100)],
        fecha_expedicion=date(2026, 1, 15),
        generado_en=datetime(2026, 1, 15, 10, 30, 0, tzinfo=MADRID),
    )
    f2 = emitir_factura(
        nif_emisor=NIF, serie="A/2026", ultimo_numero=f1.numero,
        lineas=[linea(2, "50.25", 10)],
        fecha_expedicion=date(2026, 1, 15),
        generado_en=datetime(2026, 1, 15, 10, 35, 0, tzinfo=MADRID),
        huella_anterior=f1.huella,
    )
    anul = anular_factura(
        nif_emisor=NIF,
        num_serie_factura=f2.num_serie_factura,
        fecha_expedicion=f2.fecha_expedicion,
        generado_en=datetime(2026, 1, 15, 11, 0, 0, tzinfo=MADRID),
        huella_anterior=f2.huella,
    )

    libro = [f1.cadena_verifactu, f2.cadena_verifactu, anul.cadena_verifactu]
    assert verificar_libro(libro) is True

    # las tres huellas son distintas entre si
    assert len({f1.huella, f2.huella, anul.huella}) == 3


def test_cadena_rota_se_detecta():
    f1 = emitir_factura(
        nif_emisor=NIF, serie="A/2026", ultimo_numero=0,
        lineas=[linea(1, 100)], fecha_expedicion=date(2026, 1, 15),
        generado_en=datetime(2026, 1, 15, 10, 30, tzinfo=MADRID),
    )
    # un segundo registro que NO encadena con el primero
    f2 = emitir_factura(
        nif_emisor=NIF, serie="A/2026", ultimo_numero=1,
        lineas=[linea(1, 100)], fecha_expedicion=date(2026, 1, 15),
        generado_en=datetime(2026, 1, 15, 10, 35, tzinfo=MADRID),
        huella_anterior="",  # deberia ser f1.huella
    )
    assert verificar_libro([f1.cadena_verifactu, f2.cadena_verifactu]) is False


def test_anulacion_no_puede_ser_primer_registro():
    with pytest.raises(ValueError, match="primer registro"):
        anular_factura(
            nif_emisor=NIF, num_serie_factura="A/2026-0001",
            fecha_expedicion=date(2026, 1, 15),
            generado_en=datetime(2026, 1, 15, 11, 0, tzinfo=MADRID),
            huella_anterior="",
        )


def test_importes_de_la_huella_vienen_del_calculo():
    """Los importes que entran en la huella son los del motor de calculo."""
    f = emitir_factura(
        nif_emisor=NIF, serie="A/2026", ultimo_numero=0,
        lineas=[linea(3, "33.33"), linea(1, "10", 10)],
        fecha_expedicion=date(2026, 1, 15),
        generado_en=datetime(2026, 1, 15, 10, 30, tzinfo=MADRID),
    )
    # 99.99 al 21% = 20.9979 -> 21.00 ; 10.00 al 10% = 1.00
    assert f.totales.base_imponible == Decimal("109.99")
    assert f.totales.cuota_total_str == "22.00"
    assert f.totales.importe_total_str == "131.99"


def test_reproducibilidad_misma_entrada_misma_huella():
    kw = dict(
        nif_emisor=NIF, serie="A/2026", ultimo_numero=0,
        lineas=[linea(1, 100)], fecha_expedicion=date(2026, 1, 15),
        generado_en=datetime(2026, 1, 15, 10, 30, tzinfo=MADRID),
    )
    assert emitir_factura(**kw).huella == emitir_factura(**kw).huella
