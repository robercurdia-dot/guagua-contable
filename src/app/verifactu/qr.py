"""
Codigo QR tributario de la factura y URL del servicio de cotejo.

Fuente de verdad: "Detalle de las especificaciones tecnicas del codigo QR de la
factura y de la URL del servicio de cotejo o remision de informacion por parte
del receptor de la factura", AEAT v0.5.0 (10/12/2025).
Copia en docs/aeat/AEAT_especificaciones_QR_v0.5.0.pdf

CONFIRMADO contra ese documento (ya no son suposiciones):
  - URLs base por modo y entorno (ver URLS mas abajo). OJO: el modo
    NO-VERIFACTU usa un endpoint DISTINTO (ValidarQRNoVerifactu).
  - Los cuatro parametros se llaman: nif, numserie, fecha, importe.
  - Los valores van con "URL encoding" y codificacion UTF-8.
  - Formato de fecha DD-MM-AAAA; importe NNNNNNNNN.DD.
  - Nivel de correccion de errores M (medio), ISO/IEC 18004:2015.
  - Tamano impreso entre 30x30 y 40x40 mm (art. 21 del Reglamento).
"""
from __future__ import annotations

from urllib.parse import urlencode

from .modos import ModoOperacion

# Nivel de correccion de errores exigido por el Reglamento (art. 21).
NIVEL_CORRECCION_ERRORES = "M"
# Tamano impreso admitido, en milimetros.
TAMANO_MIN_MM = 30
TAMANO_MAX_MM = 40

# URLs de cotejo: (modo, produccion) -> URL base.
URLS = {
    (ModoOperacion.VERIFACTU, False): "https://prewww2.aeat.es/wlpl/TIKE-CONT/ValidarQR",
    (ModoOperacion.VERIFACTU, True): "https://www2.agenciatributaria.gob.es/wlpl/TIKE-CONT/ValidarQR",
    (ModoOperacion.NO_VERIFACTU, False): "https://prewww2.aeat.es/wlpl/TIKE-CONT/ValidarQRNoVerifactu",
    (ModoOperacion.NO_VERIFACTU, True): "https://www2.agenciatributaria.gob.es/wlpl/TIKE-CONT/ValidarQRNoVerifactu",
}


def url_qr(
    *,
    nif_emisor: str,
    num_serie_factura: str,
    fecha_expedicion: str,     # DD-MM-AAAA
    importe_total: str,        # NNNNNNNNN.DD
    modo: ModoOperacion = ModoOperacion.VERIFACTU,
    produccion: bool = False,
) -> str:
    """
    Construye la URL de cotejo que se codifica en el QR.

    Por defecto apunta al entorno de PRUEBAS: hay que pedir produccion
    explicitamente para no imprimir facturas contra el entorno real por
    descuido.

    El "URL encoding" no es cosmetico: un numero de serie con '&' (permitido)
    rompe la URL si no se escapa a %26, y el receptor no puede cotejar la
    factura. El propio documento de la AEAT muestra ese caso como ejemplo
    erroneo.
    """
    base = URLS[(ModoOperacion(modo), produccion)]
    params = {
        "nif": nif_emisor,
        "numserie": num_serie_factura,
        "fecha": fecha_expedicion,
        "importe": importe_total,
    }
    return f"{base}?{urlencode(params)}"


def imagen_qr_png(url: str, escala: int = 4, borde: int = 2) -> bytes:
    """
    PNG del QR. Nivel de correccion M, exigido por el Reglamento.
    Al maquetar la factura hay que respetar el tamano de 30-40 mm.
    """
    import io

    import segno

    qr = segno.make(url, error=NIVEL_CORRECCION_ERRORES.lower())
    buf = io.BytesIO()
    qr.save(buf, kind="png", scale=escala, border=borde)
    return buf.getvalue()


# Leyendas que deben acompanar al QR en la factura (art. 20 y 21).
LEYENDA_VERIFACTU = "Factura verificable en la sede electronica de la AEAT"
LEYENDA_VERIFACTU_CORTA = "VERI*FACTU"
LEYENDA_QR = "QR tributario"
