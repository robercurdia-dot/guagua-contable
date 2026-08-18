"""
Cliente SOAP del servicio de suministro de registros de facturacion.

Contrato: SistemaFacturacion.wsdl (oficial AEAT).
  - SOAP 1.1, style=document, use=literal, soapAction vacio.
  - Autenticacion por CERTIFICADO ELECTRONICO (TLS mutuo), no por credenciales.
  - Endpoints en endpoints.py, extraidos del propio WSDL.

SOBRE LOS REINTENTOS (lo importante de este modulo):

Reintentar a ciegas es peligroso. Un registro que la AEAT devuelve como
"AceptadoConErrores" YA ESTA ALMACENADO; reenviarlo produce un duplicado
(error 3000). Por eso:

  - Solo se reintenta lo que fallo por RED o por error 5xx, donde no sabemos
    si la peticion llego.
  - Ante una respuesta de negocio NUNCA se reintenta automaticamente: se
    devuelve para que el llamante decida, guiado por Respuesta.a_reenviar().
  - Si la AEAT indica TiempoEsperaEnvio, hay que respetarlo antes del
    siguiente envio.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import httpx
from lxml import etree

from .endpoints import Entorno, url_suministro
from .respuesta import Respuesta, parsear
from .xml import Cabecera, RegistroAltaXML, RegistroAnulacionXML, construir_envio, validar

NS_SOAP_ENV = "http://schemas.xmlsoap.org/soap/envelope/"

# Reintentos solo para fallos de transporte.
REINTENTOS_MAX = 3
ESPERA_BASE_S = 2.0


class ErrorTransporte(RuntimeError):
    """No se pudo hablar con la AEAT (red, TLS, 5xx). Es seguro reintentar."""


class CertificadoNoConfigurado(RuntimeError):
    """Falta el certificado: sin el, la AEAT no acepta la conexion."""


@dataclass(frozen=True)
class Certificado:
    """
    Certificado para el TLS mutuo. httpx espera PEM; un .p12/.pfx de la FNMT
    hay que convertirlo antes:

        openssl pkcs12 -in cert.p12 -clcerts -nokeys -out cert.pem
        openssl pkcs12 -in cert.p12 -nocerts -nodes  -out clave.pem
    """
    ruta_cert: str
    ruta_clave: str | None = None

    def como_parametro_httpx(self):
        cert = Path(self.ruta_cert)
        if not cert.exists():
            raise CertificadoNoConfigurado(f"No existe el certificado: {cert}")
        if self.ruta_clave:
            clave = Path(self.ruta_clave)
            if not clave.exists():
                raise CertificadoNoConfigurado(f"No existe la clave: {clave}")
            return (str(cert), str(clave))
        return str(cert)


def envolver_en_soap(cuerpo: etree._Element) -> bytes:
    """Mete el RegFactuSistemaFacturacion en un sobre SOAP 1.1."""
    env = etree.Element(f"{{{NS_SOAP_ENV}}}Envelope", nsmap={"soapenv": NS_SOAP_ENV})
    etree.SubElement(env, f"{{{NS_SOAP_ENV}}}Header")
    body = etree.SubElement(env, f"{{{NS_SOAP_ENV}}}Body")
    body.append(cuerpo)
    return etree.tostring(env, xml_declaration=True, encoding="UTF-8")


class ClienteAEAT:
    """
    Cliente del web service. Por defecto apunta a PRUEBAS: hay que pedir
    produccion explicitamente.
    """

    def __init__(
        self,
        certificado: Certificado | None = None,
        *,
        entorno: Entorno = Entorno.PRUEBAS,
        certificado_sello: bool = False,
        bajo_requerimiento: bool = False,
        timeout: float = 30.0,
        transporte: httpx.BaseTransport | None = None,
    ):
        self.certificado = certificado
        self.entorno = Entorno(entorno)
        self.url = url_suministro(
            self.entorno,
            certificado_sello=certificado_sello,
            bajo_requerimiento=bajo_requerimiento,
        )
        self.timeout = timeout
        # transporte inyectable: permite probar el cliente entero sin certificado
        self._transporte = transporte

    def _cliente_http(self) -> httpx.Client:
        if self._transporte is not None:
            return httpx.Client(transport=self._transporte, timeout=self.timeout)
        if self.certificado is None:
            raise CertificadoNoConfigurado(
                "La AEAT exige certificado electronico (TLS mutuo). "
                "Se puede inyectar un transporte de prueba para no necesitarlo."
            )
        return httpx.Client(
            cert=self.certificado.como_parametro_httpx(), timeout=self.timeout
        )

    def enviar(
        self,
        cabecera: Cabecera,
        registros: list[RegistroAltaXML | RegistroAnulacionXML],
        *,
        validar_antes: bool = True,
    ) -> Respuesta:
        """
        Envia un lote y devuelve la respuesta ya interpretada.

        validar_antes: valida contra el XSD antes de salir a la red. Vale la
        pena: un XML invalido se rechaza entero (error 4102), asi que es mejor
        detectarlo aqui que gastar un viaje.
        """
        envio = construir_envio(cabecera, registros)
        if validar_antes:
            validar(envio)
        return self.enviar_xml(envolver_en_soap(envio))

    def enviar_xml(self, sobre: bytes) -> Respuesta:
        """Envia un sobre SOAP ya construido, con reintentos SOLO de transporte."""
        cabeceras = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": "",
        }
        ultimo_error: Exception | None = None
        for intento in range(1, REINTENTOS_MAX + 1):
            try:
                with self._cliente_http() as http:
                    r = http.post(self.url, content=sobre, headers=cabeceras)
                if r.status_code >= 500:
                    # el servidor fallo: no sabemos si proceso el envio, pero la
                    # AEAT descarta lo no procesado, asi que reintentar es seguro
                    raise ErrorTransporte(f"HTTP {r.status_code} de la AEAT")
                if r.status_code >= 400:
                    # error del cliente: reintentar daria lo mismo
                    raise ErrorTransporte(
                        f"HTTP {r.status_code} de la AEAT (no se reintenta): "
                        f"{r.text[:300]}"
                    )
                return parsear(r.content)
            except (httpx.TransportError, ErrorTransporte) as e:
                ultimo_error = e
                no_reintentable = isinstance(e, ErrorTransporte) and "no se reintenta" in str(e)
                if no_reintentable or intento == REINTENTOS_MAX:
                    break
                time.sleep(ESPERA_BASE_S * (2 ** (intento - 1)))  # backoff exponencial
        raise ErrorTransporte(
            f"No se pudo enviar a la AEAT tras {intento} intento(s): {ultimo_error}"
        ) from ultimo_error


def esperar_si_procede(respuesta: Respuesta, dormir=time.sleep) -> None:
    """
    Respeta el TiempoEsperaEnvio que indique la AEAT antes del siguiente envio.
    Ignorarlo puede acabar en suspension del acceso (ver error 4141).
    """
    if respuesta.tiempo_espera_envio:
        dormir(respuesta.tiempo_espera_envio)
