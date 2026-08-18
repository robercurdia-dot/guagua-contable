"""
Cliente SOAP contra respuestas simuladas con la forma real de
RespuestaSuministro.xsd.

Lo que se prueba aqui no es "que hable SOAP", sino que la SEMANTICA de la
respuesta este bien interpretada: reenviar lo que no toca genera duplicados en
la AEAT, y eso no se arregla desde el codigo.
"""
import httpx
import pytest
from lxml import etree

from app.verifactu.endpoints import Entorno
from app.verifactu.respuesta import (
    ErrorSOAP,
    EstadoEnvio,
    EstadoRegistro,
    parsear,
)
from app.verifactu.soap import (
    Certificado,
    CertificadoNoConfigurado,
    ClienteAEAT,
    ErrorTransporte,
    envolver_en_soap,
    esperar_si_procede,
)
from app.verifactu.xml import (
    Cabecera,
    Destinatario,
    DetalleDesglose,
    Encadenamiento,
    RegistroAltaXML,
    SistemaInformatico,
)

NS_SFR = "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/tike/cont/ws/RespuestaSuministro.xsd"
NS_SF = "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/tike/cont/ws/SuministroInformacion.xsd"
NS_ENV = "http://schemas.xmlsoap.org/soap/envelope/"

SIF = SistemaInformatico(
    nombre_razon="The Guagua Project SL", nif="B12345678",
    nombre_sistema="Guagua Contable", id_sistema="01",
    version="0.1.0", numero_instalacion="INST-001",
)
CAB = Cabecera(obligado_nombre="Mi Empresa SL", obligado_nif="B12345678")


def alta(num="A/2026-0001"):
    return RegistroAltaXML(
        id_emisor="B12345678", num_serie_factura=num,
        fecha_expedicion="15-01-2026", nombre_razon_emisor="Mi Empresa SL",
        tipo_factura="F1", descripcion_operacion="Servicios",
        desglose=(DetalleDesglose(base_imponible="600.00", tipo_impositivo="21",
                                  cuota_repercutida="126.00"),),
        cuota_total="126.00", importe_total="726.00",
        encadenamiento=Encadenamiento(primer_registro=True),
        sistema_informatico=SIF, fecha_hora_huso="2026-01-15T10:30:00+01:00",
        huella="9" * 64, destinatarios=(Destinatario("Cliente SA", "A87654321"),),
    )


# ---------------------------------------------- fabricar respuestas simuladas
def respuesta_xml(estado_envio, lineas, csv="CSV-123", espera=None):
    """Construye una respuesta con la forma de RespuestaSuministro.xsd."""
    env = etree.Element(f"{{{NS_ENV}}}Envelope", nsmap={"soapenv": NS_ENV})
    body = etree.SubElement(env, f"{{{NS_ENV}}}Body")
    r = etree.SubElement(body, f"{{{NS_SFR}}}RespuestaRegFactuSistemaFacturacion")
    if csv:
        etree.SubElement(r, f"{{{NS_SFR}}}CSV").text = csv
    dp = etree.SubElement(r, f"{{{NS_SF}}}DatosPresentacion")
    etree.SubElement(dp, f"{{{NS_SF}}}NIFPresentador").text = "B12345678"
    if espera is not None:
        etree.SubElement(r, f"{{{NS_SFR}}}TiempoEsperaEnvio").text = str(espera)
    etree.SubElement(r, f"{{{NS_SFR}}}EstadoEnvio").text = estado_envio
    for num, estado, cod, desc in lineas:
        ln = etree.SubElement(r, f"{{{NS_SFR}}}RespuestaLinea")
        idf = etree.SubElement(ln, f"{{{NS_SF}}}IDFactura")
        etree.SubElement(idf, f"{{{NS_SF}}}NumSerieFactura").text = num
        etree.SubElement(ln, f"{{{NS_SFR}}}EstadoRegistro").text = estado
        if cod:
            etree.SubElement(ln, f"{{{NS_SFR}}}CodigoErrorRegistro").text = str(cod)
        if desc:
            etree.SubElement(ln, f"{{{NS_SFR}}}DescripcionErrorRegistro").text = desc
    return etree.tostring(env, xml_declaration=True, encoding="UTF-8")


def cliente_con(respuesta_bytes=None, status=200, handler=None):
    def por_defecto(request):
        return httpx.Response(status, content=respuesta_bytes or b"")
    return ClienteAEAT(transporte=httpx.MockTransport(handler or por_defecto))


# ---------------------------------------------------------------- envoltura
def test_envuelve_en_soap_11():
    sobre = envolver_en_soap(etree.Element("prueba"))
    raiz = etree.fromstring(sobre)
    assert raiz.tag == f"{{{NS_ENV}}}Envelope"
    assert raiz.find(f"{{{NS_ENV}}}Body/prueba") is not None


def test_cabeceras_soap_correctas():
    vistas = {}

    def handler(request):
        vistas.update(dict(request.headers))
        vistas["url"] = str(request.url)
        return httpx.Response(200, content=respuesta_xml("Correcto", []))

    cliente_con(handler=handler).enviar(CAB, [alta()])
    assert vistas["content-type"] == "text/xml; charset=utf-8"
    assert vistas["soapaction"] == ""
    assert vistas["url"] == "https://prewww1.aeat.es/wlpl/TIKE-CONT/ws/SistemaFacturacion/VerifactuSOAP"


def test_por_defecto_va_a_pruebas():
    assert "prewww1.aeat.es" in ClienteAEAT(transporte=httpx.MockTransport(lambda r: None)).url


def test_produccion_hay_que_pedirla_explicitamente():
    c = ClienteAEAT(entorno=Entorno.PRODUCCION,
                    transporte=httpx.MockTransport(lambda r: None))
    assert "www1.agenciatributaria.gob.es" in c.url


def test_valida_el_xml_antes_de_salir_a_la_red():
    """Un XML invalido se rechaza entero (4102): mejor cazarlo sin gastar viaje."""
    llamado = []

    def handler(request):
        llamado.append(1)
        return httpx.Response(200, content=respuesta_xml("Correcto", []))

    malo = alta()
    object.__setattr__(malo, "tipo_factura", "XX")  # tipo inexistente en el XSD
    with pytest.raises(ValueError, match="no cumple el XSD"):
        cliente_con(handler=handler).enviar(CAB, [malo])
    assert not llamado, "no deberia haber llamado a la AEAT"


# ---------------------------------------------------------------- semantica
def test_envio_todo_correcto():
    r = parsear(respuesta_xml("Correcto", [("A/2026-0001", "Correcto", None, None)]))
    assert r.estado_envio is EstadoEnvio.CORRECTO
    assert r.todo_correcto and not r.envio_rechazado_entero
    assert r.csv == "CSV-123"
    assert r.a_reenviar() == () and r.a_subsanar() == ()


def test_aceptado_con_errores_NO_se_reenvia():
    """
    EL CASO PELIGROSO: el registro esta almacenado en la AEAT. Reenviarlo
    genera un duplicado (error 3000).
    """
    r = parsear(respuesta_xml("Correcto", [
        ("A/2026-0001", "AceptadoConErrores", 2000, "El calculo de la huella es incorrecto"),
    ]))
    ln = r.lineas[0]
    assert ln.estado is EstadoRegistro.ACEPTADO_CON_ERRORES
    assert ln.almacenado_en_aeat is True
    assert ln.debe_reenviarse is False
    assert ln.necesita_subsanacion is True
    assert r.a_reenviar() == ()
    assert len(r.a_subsanar()) == 1


def test_incorrecto_si_se_reenvia():
    r = parsear(respuesta_xml("Incorrecto", [
        ("A/2026-0001", "Incorrecto", 1106, "TipoFactura no permitido"),
    ]))
    ln = r.lineas[0]
    assert ln.almacenado_en_aeat is False
    assert ln.debe_reenviarse is True
    assert r.envio_rechazado_entero
    assert len(r.a_reenviar()) == 1


def test_parcialmente_correcto_separa_bien_los_casos():
    """Solo se reenvia el rechazado; el aceptado-con-errores se subsana."""
    r = parsear(respuesta_xml("ParcialmenteCorrecto", [
        ("A/2026-0001", "Correcto", None, None),
        ("A/2026-0002", "Incorrecto", 1104, "NumSerieFactura incorrecto"),
        ("A/2026-0003", "AceptadoConErrores", 2001, "NIF no identificado"),
    ]))
    assert r.estado_envio is EstadoEnvio.PARCIAL
    assert [ln.num_serie_factura for ln in r.a_reenviar()] == ["A/2026-0002"]
    assert [ln.num_serie_factura for ln in r.a_subsanar()] == ["A/2026-0003"]


def test_descripcion_se_completa_con_el_catalogo_oficial():
    """Si la AEAT no manda descripcion, se saca de errores.properties."""
    r = parsear(respuesta_xml("Incorrecto", [("A/1", "Incorrecto", 4102, None)]))
    assert "esquema" in r.lineas[0].descripcion_error.lower()


def test_registro_duplicado_se_expone():
    xml = respuesta_xml("Incorrecto", [("A/1", "Incorrecto", 3000, "Duplicado")])
    raiz = etree.fromstring(xml)
    ln = raiz.find(f".//{{{NS_SFR}}}RespuestaLinea")
    dup = etree.SubElement(ln, f"{{{NS_SF}}}RegistroDuplicado")
    etree.SubElement(dup, f"{{{NS_SF}}}IdPeticionRegistroDuplicado").text = "PET-99"
    r = parsear(etree.tostring(raiz))
    assert r.lineas[0].duplicado_id_peticion == "PET-99"


def test_tiempo_de_espera_se_respeta():
    r = parsear(respuesta_xml("Correcto", [], espera=60))
    assert r.tiempo_espera_envio == 60
    dormido = []
    esperar_si_procede(r, dormir=dormido.append)
    assert dormido == [60]


def test_sin_tiempo_de_espera_no_duerme():
    dormido = []
    esperar_si_procede(parsear(respuesta_xml("Correcto", [])), dormir=dormido.append)
    assert dormido == []


# ---------------------------------------------------------------- errores
def test_soap_fault_se_detecta():
    env = etree.Element(f"{{{NS_ENV}}}Envelope", nsmap={"soapenv": NS_ENV})
    body = etree.SubElement(env, f"{{{NS_ENV}}}Body")
    fault = etree.SubElement(body, f"{{{NS_ENV}}}Fault")
    etree.SubElement(fault, "faultcode").text = "soapenv:Server"
    etree.SubElement(fault, "faultstring").text = "Certificado no valido"
    with pytest.raises(ErrorSOAP, match="Certificado no valido"):
        parsear(etree.tostring(env))


def test_respuesta_sin_estado_es_invalida():
    with pytest.raises(ValueError, match="EstadoEnvio"):
        parsear(b"<vacio/>")


def test_sin_certificado_ni_transporte_falla_claro():
    with pytest.raises(CertificadoNoConfigurado, match="certificado"):
        ClienteAEAT().enviar(CAB, [alta()])


def test_certificado_inexistente_se_detecta():
    with pytest.raises(CertificadoNoConfigurado, match="No existe el certificado"):
        Certificado(ruta_cert="/no/existe.pem").como_parametro_httpx()


def test_error_5xx_se_reintenta(monkeypatch):
    monkeypatch.setattr("app.verifactu.soap.time.sleep", lambda s: None)
    intentos = []

    def handler(request):
        intentos.append(1)
        return httpx.Response(503, content=b"")

    with pytest.raises(ErrorTransporte, match="3 intento"):
        cliente_con(handler=handler).enviar(CAB, [alta()])
    assert len(intentos) == 3


def test_error_4xx_no_se_reintenta():
    intentos = []

    def handler(request):
        intentos.append(1)
        return httpx.Response(400, content=b"peticion mal formada")

    with pytest.raises(ErrorTransporte, match="no se reintenta"):
        cliente_con(handler=handler).enviar(CAB, [alta()])
    assert len(intentos) == 1, "un 400 no mejora reintentando"


def test_fallo_de_red_se_reintenta_y_acaba_rindiendose(monkeypatch):
    monkeypatch.setattr("app.verifactu.soap.time.sleep", lambda s: None)
    intentos = []

    def handler(request):
        intentos.append(1)
        raise httpx.ConnectError("sin ruta al host")

    with pytest.raises(ErrorTransporte, match="No se pudo enviar"):
        cliente_con(handler=handler).enviar(CAB, [alta()])
    assert len(intentos) == 3


def test_una_respuesta_de_negocio_nunca_se_reintenta():
    """Un rechazo de negocio es determinista: reintentarlo solo duplica riesgo."""
    intentos = []

    def handler(request):
        intentos.append(1)
        return httpx.Response(200, content=respuesta_xml(
            "Incorrecto", [("A/2026-0001", "Incorrecto", 1106, "malo")]))

    r = cliente_con(handler=handler).enviar(CAB, [alta()])
    assert len(intentos) == 1
    assert r.envio_rechazado_entero
