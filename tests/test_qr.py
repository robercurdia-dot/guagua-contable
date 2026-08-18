"""
Tests del QR, contrastados con la spec oficial AEAT v0.5.0.
El vector de ejemplo esta copiado literalmente del documento.
"""
import pytest

from app.verifactu.modos import ModoOperacion
from app.verifactu.qr import (
    NIVEL_CORRECCION_ERRORES,
    TAMANO_MAX_MM,
    TAMANO_MIN_MM,
    imagen_qr_png,
    url_qr,
)

# ---- Vector oficial (apartado 4 del documento AEAT) --------------------
# Parametros: nif=89890001K, numserie=12345678&G33, fecha=01-01-2024,
#             importe=241.4  (entorno de Pruebas Externas)
VECTOR_OFICIAL_ENTRADA = dict(
    nif_emisor="89890001K",
    num_serie_factura="12345678&G33",
    fecha_expedicion="01-01-2024",
    importe_total="241.4",
)
VECTOR_OFICIAL_URL = (
    "https://prewww2.aeat.es/wlpl/TIKE-CONT/ValidarQR"
    "?nif=89890001K&numserie=12345678%26G33&fecha=01-01-2024&importe=241.4"
)


def test_vector_oficial_de_la_aeat():
    """GATE: debe reproducir exactamente la URL del ejemplo oficial."""
    assert url_qr(**VECTOR_OFICIAL_ENTRADA) == VECTOR_OFICIAL_URL


def test_ampersand_en_num_serie_se_escapa():
    """
    El documento muestra como ERRONEA la URL sin escapar. Un '&' sin escapar
    parte la query y el receptor no puede cotejar la factura.
    """
    u = url_qr(**VECTOR_OFICIAL_ENTRADA)
    assert "%26G33" in u
    assert "&G33" not in u.replace("%26G33", "")


# ---- URLs por modo y entorno ------------------------------------------
def test_por_defecto_apunta_a_pruebas():
    assert url_qr(**VECTOR_OFICIAL_ENTRADA).startswith("https://prewww2.aeat.es/")


def test_produccion_verifactu():
    u = url_qr(**VECTOR_OFICIAL_ENTRADA, produccion=True)
    assert u.startswith("https://www2.agenciatributaria.gob.es/wlpl/TIKE-CONT/ValidarQR?")


def test_no_verifactu_usa_endpoint_distinto():
    """Hallazgo de la spec: No-Verifactu NO usa el mismo endpoint."""
    u = url_qr(**VECTOR_OFICIAL_ENTRADA, modo=ModoOperacion.NO_VERIFACTU)
    assert "/ValidarQRNoVerifactu?" in u
    v = url_qr(**VECTOR_OFICIAL_ENTRADA, modo=ModoOperacion.VERIFACTU)
    assert "/ValidarQR?" in v and "NoVerifactu" not in v


def test_los_cuatro_parametros_y_su_orden():
    u = url_qr(**VECTOR_OFICIAL_ENTRADA)
    query = u.split("?", 1)[1]
    assert [p.split("=")[0] for p in query.split("&")] == [
        "nif", "numserie", "fecha", "importe",
    ]


# ---- Caracteristicas del QR -------------------------------------------
def test_nivel_de_correccion_es_m():
    """El Reglamento (art. 21) exige nivel M, no L."""
    assert NIVEL_CORRECCION_ERRORES == "M"


def test_tamano_reglamentario():
    assert (TAMANO_MIN_MM, TAMANO_MAX_MM) == (30, 40)


def test_genera_png_valido():
    png = imagen_qr_png(url_qr(**VECTOR_OFICIAL_ENTRADA))
    assert png.startswith(b"\x89PNG\r\n\x1a\n")


def test_modo_invalido_falla():
    with pytest.raises(ValueError):
        url_qr(**VECTOR_OFICIAL_ENTRADA, modo="INVENTADO")
