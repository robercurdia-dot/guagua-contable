"""
Generacion del codigo QR tributario de la factura.

El QR contiene una URL al servicio de cotejo de la sede electronica de la AEAT
con los datos de la factura como parametros de query. La URL base cambia entre
el entorno de PRUEBAS y el de PRODUCCION.

AVISO: las URLs base y el nombre exacto de los parametros deben confirmarse
contra la documentacion vigente de la AEAT antes de produccion.
"""
from __future__ import annotations

from urllib.parse import urlencode

# URLs de cotejo (confirmar contra doc vigente AEAT antes de produccion).
URL_COTEJO_PRUEBAS = "https://prewww2.aeat.es/wlpl/TIKE-CONT/ValidarQR"
URL_COTEJO_PRODUCCION = "https://www2.agenciatributaria.gob.es/wlpl/TIKE-CONT/ValidarQR"


def url_qr(
    *,
    nif_emisor: str,
    num_serie_factura: str,
    fecha_expedicion: str,     # dd-mm-aaaa
    importe_total: str,
    produccion: bool = False,
) -> str:
    """Construye la URL de cotejo que se codifica en el QR."""
    base = URL_COTEJO_PRODUCCION if produccion else URL_COTEJO_PRUEBAS
    params = {
        "nif": nif_emisor,
        "numserie": num_serie_factura,
        "fecha": fecha_expedicion,
        "importe": importe_total,
    }
    return f"{base}?{urlencode(params)}"


def imagen_qr_png(url: str) -> bytes:
    """
    Genera el PNG del QR a partir de la URL de cotejo.
    Usa 'segno' (dependencia pura Python) con nivel de correccion de error 'M'.
    """
    import segno  # import perezoso para no acoplar el modulo a la libreria

    qr = segno.make(url, error="m")
    import io
    buf = io.BytesIO()
    qr.save(buf, kind="png", scale=4, border=2)
    return buf.getvalue()


# Leyendas obligatorias en la factura.
LEYENDA_VERIFACTU = "VERI*FACTU - Factura verificable en la sede electronica de la AEAT"
LEYENDA_QR = "QR tributario"
