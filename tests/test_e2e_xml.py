"""
End-to-end: emitir facturas encadenadas -> construir el XML -> validarlo
contra el XSD OFICIAL de la AEAT. Es la prueba de que las dos mitades
(dominio de facturacion y motor Verifactu) encajan.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.facturacion import LineaCalculo, emitir_factura, fecha_aeat, verificar_libro
from app.verifactu.xml import (
    Cabecera,
    Destinatario,
    DetalleDesglose,
    RegistroAltaXML,
    SistemaInformatico,
    construir_envio,
    validar,
)

TZ = timezone(timedelta(hours=1))
NIF = "B12345678"
SIF = SistemaInformatico(
    nombre_razon="The Guagua Project SL", nif=NIF,
    nombre_sistema="Guagua Contable", id_sistema="01",
    version="0.1.0", numero_instalacion="INST-001",
)
CAB = Cabecera(obligado_nombre="Mi Empresa SL", obligado_nif=NIF)
CLIENTE = Destinatario(nombre_razon="Cliente SA", nif="A87654321")


def desglose_desde_totales(totales):
    """Mapea el desglose calculado al DetalleDesglose del XML."""
    detalles = []
    for d in totales.desglose:
        if d.tipo_iva == 0:
            detalles.append(DetalleDesglose(
                base_imponible=str(d.base),
                calificacion_operacion=None, operacion_exenta="E1"))
        else:
            detalles.append(DetalleDesglose(
                base_imponible=str(d.base),
                tipo_impositivo=str(d.tipo_iva),
                cuota_repercutida=str(d.cuota),
                tipo_recargo=str(d.tipo_recargo) if d.cuota_recargo else None,
                cuota_recargo=str(d.cuota_recargo) if d.cuota_recargo else None,
            ))
    return tuple(detalles)


def a_registro_xml(f):
    return RegistroAltaXML(
        id_emisor=f.nif_emisor,
        num_serie_factura=f.num_serie_factura,
        fecha_expedicion=fecha_aeat(f.fecha_expedicion),
        nombre_razon_emisor="Mi Empresa SL",
        tipo_factura=f.tipo_factura,
        descripcion_operacion="Servicios profesionales",
        desglose=desglose_desde_totales(f.totales),
        cuota_total=f.totales.cuota_total_str,
        importe_total=f.totales.importe_total_str,
        encadenamiento=f.encadenamiento,
        sistema_informatico=SIF,
        fecha_hora_huso=f.fecha_hora_huso,
        huella=f.huella,
        destinatarios=(CLIENTE,),
    )


def test_libro_encadenado_genera_xml_valido():
    """Tres facturas encadenadas; el lote completo valida contra el XSD."""
    casos = [
        [LineaCalculo("Consultoria", Decimal("10"), Decimal("60"))],
        [LineaCalculo("Diseno", Decimal("1"), Decimal("250")),
         LineaCalculo("Manual", Decimal("2"), Decimal("14.90"), Decimal("10"))],
        [LineaCalculo("Material", Decimal("7"), Decimal("12.35"),
                      Decimal("21"), con_recargo=True)],
    ]
    facturas, huella, ultimo, anterior = [], "", 0, None
    for i, lineas in enumerate(casos):
        f = emitir_factura(
            nif_emisor=NIF, serie="A/2026", ultimo_numero=ultimo, lineas=lineas,
            fecha_expedicion=date(2026, 1, 15 + i),
            generado_en=datetime(2026, 1, 15 + i, 10, 0, 0, tzinfo=TZ),
            huella_anterior=huella, registro_anterior=anterior,
        )
        facturas.append(f)
        huella, ultimo, anterior = f.huella, f.numero, f.como_registro_anterior()

    # la cadena de huellas es integra
    assert verificar_libro([f.cadena_verifactu for f in facturas]) is True
    # y el XML del lote valida contra el esquema oficial
    validar(construir_envio(CAB, [a_registro_xml(f) for f in facturas]))


def test_primera_factura_usa_primer_registro():
    f = emitir_factura(
        nif_emisor=NIF, serie="A/2026", ultimo_numero=0,
        lineas=[LineaCalculo("x", Decimal("1"), Decimal("100"))],
        fecha_expedicion=date(2026, 1, 15),
        generado_en=datetime(2026, 1, 15, 10, 0, tzinfo=TZ),
    )
    assert f.encadenamiento.primer_registro is True
    validar(construir_envio(CAB, [a_registro_xml(f)]))


def test_segunda_factura_referencia_a_la_anterior():
    f1 = emitir_factura(
        nif_emisor=NIF, serie="A/2026", ultimo_numero=0,
        lineas=[LineaCalculo("x", Decimal("1"), Decimal("100"))],
        fecha_expedicion=date(2026, 1, 15),
        generado_en=datetime(2026, 1, 15, 10, 0, tzinfo=TZ),
    )
    f2 = emitir_factura(
        nif_emisor=NIF, serie="A/2026", ultimo_numero=1,
        lineas=[LineaCalculo("x", Decimal("1"), Decimal("100"))],
        fecha_expedicion=date(2026, 1, 16),
        generado_en=datetime(2026, 1, 16, 10, 0, tzinfo=TZ),
        huella_anterior=f1.huella, registro_anterior=f1.como_registro_anterior(),
    )
    enc = f2.encadenamiento
    assert enc.primer_registro is False
    assert enc.anterior.huella == f1.huella
    assert enc.anterior.num_serie_factura == "A/2026-0001"
    assert enc.anterior.fecha_expedicion == "15-01-2026"


def test_registro_no_inicial_sin_identidad_del_anterior_falla():
    """Arrastrar solo la huella no basta para construir el XML."""
    f = emitir_factura(
        nif_emisor=NIF, serie="A/2026", ultimo_numero=1,
        lineas=[LineaCalculo("x", Decimal("1"), Decimal("100"))],
        fecha_expedicion=date(2026, 1, 16),
        generado_en=datetime(2026, 1, 16, 10, 0, tzinfo=TZ),
        huella_anterior="A" * 64,  # sin registro_anterior
    )
    with pytest.raises(ValueError, match="no solo su huella"):
        _ = f.encadenamiento


def test_huella_anterior_incoherente_se_detecta():
    from app.verifactu.xml import RegistroAnterior
    with pytest.raises(ValueError, match="Incoherencia"):
        emitir_factura(
            nif_emisor=NIF, serie="A/2026", ultimo_numero=1,
            lineas=[LineaCalculo("x", Decimal("1"), Decimal("100"))],
            fecha_expedicion=date(2026, 1, 16),
            generado_en=datetime(2026, 1, 16, 10, 0, tzinfo=TZ),
            huella_anterior="A" * 64,
            registro_anterior=RegistroAnterior(NIF, "A/2026-0001", "15-01-2026", "B" * 64),
        )
