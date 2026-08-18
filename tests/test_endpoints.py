"""Endpoints AEAT, contrastados con SistemaFacturacion.wsdl."""
import re
from pathlib import Path

from app.verifactu.endpoints import REQUERIMIENTO, VERIFACTU, Entorno, url_suministro

WSDL = Path("src/app/verifactu/schemas/SistemaFacturacion.wsdl")


def test_por_defecto_apunta_a_pruebas():
    """Nunca produccion por descuido."""
    assert "prewww1.aeat.es" in url_suministro()


def test_todas_las_urls_estan_en_el_wsdl_oficial():
    declaradas = set(re.findall(r'soap:address location="([^"]+)"', WSDL.read_text()))
    assert set(VERIFACTU.values()) | set(REQUERIMIENTO.values()) <= declaradas


def test_variante_certificado_de_sello():
    assert "www10" in url_suministro(Entorno.PRODUCCION, certificado_sello=True)
    assert "www1." in url_suministro(Entorno.PRODUCCION, certificado_sello=False)


def test_requerimiento_usa_endpoint_distinto():
    assert url_suministro(bajo_requerimiento=True).endswith("RequerimientoSOAP")
    assert url_suministro().endswith("VerifactuSOAP")
