"""
Tests de serializacion XML contra el XSD OFICIAL de la AEAT.

Estos tests son el gate de la epica E1: si el XML no valida, la AEAT rechaza el
envio completo con el error 4102.
"""
import pytest
from lxml import etree

from app.verifactu.xml import (
    MAX_DETALLES_DESGLOSE,
    Cabecera,
    Destinatario,
    DetalleDesglose,
    Encadenamiento,
    RegistroAltaXML,
    RegistroAnterior,
    RegistroAnulacionXML,
    SistemaInformatico,
    a_bytes,
    construir_envio,
    validar,
)

SIF = SistemaInformatico(
    nombre_razon="The Guagua Project SL", nif="B12345678",
    nombre_sistema="Guagua Contable", id_sistema="01",
    version="0.1.0", numero_instalacion="INST-001",
)
CAB = Cabecera(obligado_nombre="Mi Empresa SL", obligado_nif="B12345678")
CLIENTE = Destinatario(nombre_razon="Cliente SA", nif="A87654321")
HUELLA = "9" * 64


def alta(**kw):
    base = dict(
        id_emisor="B12345678", num_serie_factura="A/2026-0001",
        fecha_expedicion="15-01-2026", nombre_razon_emisor="Mi Empresa SL",
        tipo_factura="F1", descripcion_operacion="Servicios",
        desglose=(DetalleDesglose(base_imponible="600.00", tipo_impositivo="21",
                                  cuota_repercutida="126.00"),),
        cuota_total="126.00", importe_total="726.00",
        encadenamiento=Encadenamiento(primer_registro=True),
        sistema_informatico=SIF, fecha_hora_huso="2026-01-15T10:30:00+01:00",
        huella=HUELLA, destinatarios=(CLIENTE,),
    )
    base.update(kw)
    return RegistroAltaXML(**base)


# ------------------------------------------------- validacion contra el XSD
def test_alta_valida_contra_xsd_oficial():
    validar(construir_envio(CAB, [alta()]))


def test_anulacion_valida_contra_xsd_oficial():
    anu = RegistroAnulacionXML(
        id_emisor="B12345678", num_serie_factura="A/2026-0001",
        fecha_expedicion="15-01-2026",
        encadenamiento=Encadenamiento(anterior=RegistroAnterior(
            id_emisor="B12345678", num_serie_factura="A/2026-0001",
            fecha_expedicion="15-01-2026", huella=HUELLA)),
        sistema_informatico=SIF, fecha_hora_huso="2026-01-20T09:00:00+01:00",
        huella="A" * 64,
    )
    validar(construir_envio(CAB, [anu]))


def test_encadenado_a_registro_anterior_valida():
    a = alta(encadenamiento=Encadenamiento(anterior=RegistroAnterior(
        id_emisor="B12345678", num_serie_factura="A/2026-0001",
        fecha_expedicion="15-01-2026", huella=HUELLA)))
    validar(construir_envio(CAB, [a]))


def test_lote_de_varios_registros_valida():
    validar(construir_envio(CAB, [alta(), alta(num_serie_factura="A/2026-0002")]))


def test_factura_exenta_valida():
    a = alta(
        desglose=(DetalleDesglose(base_imponible="400.00",
                                  calificacion_operacion=None,
                                  operacion_exenta="E1"),),
        cuota_total="0.00", importe_total="400.00",
    )
    validar(construir_envio(CAB, [a]))


def test_con_recargo_equivalencia_valida():
    a = alta(desglose=(DetalleDesglose(
        base_imponible="100.00", tipo_impositivo="21", cuota_repercutida="21.00",
        tipo_recargo="5.2", cuota_recargo="5.20"),),
        cuota_total="26.20", importe_total="126.20")
    validar(construir_envio(CAB, [a]))


def test_simplificada_f2_sin_destinatarios_valida():
    validar(construir_envio(CAB, [alta(tipo_factura="F2", destinatarios=())]))


def test_representante_en_cabecera_valida():
    cab = Cabecera(obligado_nombre="Mi Empresa SL", obligado_nif="B12345678",
                   representante_nombre="Asesoria SL", representante_nif="B11111111")
    validar(construir_envio(cab, [alta()]))


# ------------------------------------------------- estructura del XML
def test_orden_de_elementos_es_el_del_xsd():
    envio = construir_envio(CAB, [alta()])
    ns = "{https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/tike/cont/ws/SuministroInformacion.xsd}"
    reg = envio.find(f".//{ns}RegistroAlta")
    tags = [etree.QName(h).localname for h in reg]
    assert tags == [
        "IDVersion", "IDFactura", "NombreRazonEmisor", "TipoFactura",
        "DescripcionOperacion", "Destinatarios", "Desglose", "CuotaTotal",
        "ImporteTotal", "Encadenamiento", "SistemaInformatico",
        "FechaHoraHusoGenRegistro", "TipoHuella", "Huella",
    ]


def test_xml_lleva_declaracion_utf8():
    assert a_bytes(construir_envio(CAB, [alta()])).startswith(b"<?xml version='1.0' encoding='UTF-8'?>")


# ------------------------------------------------- reglas de negocio AEAT
def test_f1_sin_destinatarios_falla():
    with pytest.raises(ValueError, match="1189"):
        alta(destinatarios=())


def test_f2_con_destinatarios_falla():
    with pytest.raises(ValueError, match="1190"):
        alta(tipo_factura="F2")


def test_desglose_supera_el_maximo_del_xsd():
    det = DetalleDesglose(base_imponible="1.00", tipo_impositivo="21", cuota_repercutida="0.21")
    with pytest.raises(ValueError, match="entre 1 y 12"):
        alta(desglose=tuple([det] * (MAX_DETALLES_DESGLOSE + 1)))


def test_desglose_vacio_falla():
    with pytest.raises(ValueError, match="entre 1 y 12"):
        alta(desglose=())


def test_calificacion_y_exenta_son_excluyentes():
    with pytest.raises(ValueError, match="1195|1196"):
        DetalleDesglose(base_imponible="1.00", calificacion_operacion="S1",
                        operacion_exenta="E1")
    with pytest.raises(ValueError, match="1195|1196"):
        DetalleDesglose(base_imponible="1.00", calificacion_operacion=None)


def test_exenta_no_admite_tipo_impositivo():
    with pytest.raises(ValueError, match="1238"):
        DetalleDesglose(base_imponible="1.00", calificacion_operacion=None,
                        operacion_exenta="E1", tipo_impositivo="21")


def test_recargo_tipo_y_cuota_van_juntos():
    with pytest.raises(ValueError, match="1284"):
        DetalleDesglose(base_imponible="1.00", tipo_impositivo="21",
                        cuota_repercutida="0.21", tipo_recargo="5.2")


def test_encadenamiento_exige_exactamente_una_opcion():
    with pytest.raises(ValueError, match="exactamente uno"):
        Encadenamiento()
    with pytest.raises(ValueError, match="exactamente uno"):
        Encadenamiento(primer_registro=True,
                       anterior=RegistroAnterior("B12345678", "A/1", "15-01-2026", HUELLA))


def test_envio_vacio_falla():
    with pytest.raises(ValueError, match="al menos un registro"):
        construir_envio(CAB, [])


def test_xml_invalido_es_detectado_por_validar():
    """Si se corrompe el XML, validar() debe cazarlo antes de enviarlo."""
    envio = construir_envio(CAB, [alta()])
    ns = "{https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/tike/cont/ws/SuministroInformacion.xsd}"
    reg = envio.find(f".//{ns}RegistroAlta")
    reg.remove(reg.find(f"{ns}TipoFactura"))  # quitar campo obligatorio
    with pytest.raises(ValueError, match="no cumple el XSD"):
        validar(envio)
