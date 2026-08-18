"""
Endpoints del web service de la AEAT.

CONFIRMADOS: extraidos literalmente de SistemaFacturacion.wsdl (oficial AEAT).
Hay dos variantes de acceso segun el tipo de certificado:
  - normal (www1 / prewww1): certificado de persona fisica o representante
  - sello  (www10 / prewww10): certificado de sello de entidad
"""
from __future__ import annotations

import enum


class Entorno(enum.StrEnum):
    PRUEBAS = "pruebas"
    PRODUCCION = "produccion"


# Sistemas VERI*FACTU (remision de registros de facturacion).
VERIFACTU = {
    (Entorno.PRODUCCION, False): "https://www1.agenciatributaria.gob.es/wlpl/TIKE-CONT/ws/SistemaFacturacion/VerifactuSOAP",
    (Entorno.PRODUCCION, True): "https://www10.agenciatributaria.gob.es/wlpl/TIKE-CONT/ws/SistemaFacturacion/VerifactuSOAP",
    (Entorno.PRUEBAS, False): "https://prewww1.aeat.es/wlpl/TIKE-CONT/ws/SistemaFacturacion/VerifactuSOAP",
    (Entorno.PRUEBAS, True): "https://prewww10.aeat.es/wlpl/TIKE-CONT/ws/SistemaFacturacion/VerifactuSOAP",
}

# Sistemas NO verificables: remision solo bajo requerimiento de la AEAT.
REQUERIMIENTO = {
    (Entorno.PRODUCCION, False): "https://www1.agenciatributaria.gob.es/wlpl/TIKE-CONT/ws/SistemaFacturacion/RequerimientoSOAP",
    (Entorno.PRODUCCION, True): "https://www10.agenciatributaria.gob.es/wlpl/TIKE-CONT/ws/SistemaFacturacion/RequerimientoSOAP",
    (Entorno.PRUEBAS, False): "https://prewww1.aeat.es/wlpl/TIKE-CONT/ws/SistemaFacturacion/RequerimientoSOAP",
    (Entorno.PRUEBAS, True): "https://prewww10.aeat.es/wlpl/TIKE-CONT/ws/SistemaFacturacion/RequerimientoSOAP",
}


def url_suministro(
    entorno: Entorno = Entorno.PRUEBAS,
    *,
    certificado_sello: bool = False,
    bajo_requerimiento: bool = False,
) -> str:
    """URL del web service a usar. Por defecto, PRUEBAS (nunca produccion por accidente)."""
    tabla = REQUERIMIENTO if bajo_requerimiento else VERIFACTU
    return tabla[(Entorno(entorno), certificado_sello)]
