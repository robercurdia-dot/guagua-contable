"""
GATE DE LA FASE 0 — vectores de ejemplo OFICIALES de la AEAT.

Fuente: AEAT, "Detalle de las especificaciones tecnicas para generacion de la
huella o hash de los registros de facturacion", version 0.1.2 (27/08/2024),
apartado 6 "Ejemplos".

Si alguno de estos tests falla, el motor NO cumple la especificacion y los
registros serian marcados por la AEAT como "Aceptado con errores".
NO tocar los valores esperados: son los publicados por la AEAT.
"""
from app.verifactu import (
    cadena_alta,
    cadena_anulacion,
    huella_registro_alta,
    huella_registro_anulacion,
)

# Huellas publicadas por la AEAT
HUELLA_CASO_1 = "3C464DAF61ACB827C65FDA19F352A4E3BDC2C640E9E9FC4CC058073F38F12F60"
HUELLA_CASO_2 = "F7B94CFD8924EDFF273501B01EE5153E4CE8F259766F88CF6ACB8935802A2B97"
HUELLA_CASO_3 = "177547C0D57AC74748561D054A9CEC14B4C4EA23D1BEFD6F2E69E3A388F90C68"

CASO_1 = dict(
    id_emisor="89890001K",
    num_serie_factura="12345678/G33",
    fecha_expedicion="01-01-2024",
    tipo_factura="F1",
    cuota_total="12.35",
    importe_total="123.45",
    fecha_hora_huso="2024-01-01T19:20:30+01:00",
)

CASO_2 = dict(
    id_emisor="89890001K",
    num_serie_factura="12345679/G34",
    fecha_expedicion="01-01-2024",
    tipo_factura="F1",
    cuota_total="12.35",
    importe_total="123.45",
    fecha_hora_huso="2024-01-01T19:20:35+01:00",
    huella_anterior=HUELLA_CASO_1,
)

CASO_3 = dict(
    id_emisor="89890001K",
    num_serie_factura="12345679/G34",
    fecha_expedicion="01-01-2024",
    fecha_hora_huso="2024-01-01T19:20:40+01:00",
    huella_anterior=HUELLA_CASO_2,
)


def test_caso_1_primer_registro_de_alta():
    """Primer registro del SIF: no hay huella anterior -> 'Huella=' vacio."""
    assert huella_registro_alta(**CASO_1) == HUELLA_CASO_1


def test_caso_1_cadena_de_entrada_literal():
    """La cadena concatenada debe ser exactamente la del documento oficial."""
    esperada = (
        "IDEmisorFactura=89890001K"
        "&NumSerieFactura=12345678/G33"
        "&FechaExpedicionFactura=01-01-2024"
        "&TipoFactura=F1"
        "&CuotaTotal=12.35"
        "&ImporteTotal=123.45"
        "&Huella="
        "&FechaHoraHusoGenRegistro=2024-01-01T19:20:30+01:00"
    )
    assert cadena_alta(**CASO_1) == esperada


def test_caso_2_alta_encadenada():
    assert huella_registro_alta(**CASO_2) == HUELLA_CASO_2


def test_caso_2_cadena_de_entrada_literal():
    esperada = (
        "IDEmisorFactura=89890001K"
        "&NumSerieFactura=12345679/G34"
        "&FechaExpedicionFactura=01-01-2024"
        "&TipoFactura=F1"
        "&CuotaTotal=12.35"
        "&ImporteTotal=123.45"
        f"&Huella={HUELLA_CASO_1}"
        "&FechaHoraHusoGenRegistro=2024-01-01T19:20:35+01:00"
    )
    assert cadena_alta(**CASO_2) == esperada


def test_caso_3_anulacion_encadenada():
    assert huella_registro_anulacion(**CASO_3) == HUELLA_CASO_3


def test_caso_3_cadena_de_entrada_literal():
    esperada = (
        "IDEmisorFacturaAnulada=89890001K"
        "&NumSerieFacturaAnulada=12345679/G34"
        "&FechaExpedicionFacturaAnulada=01-01-2024"
        f"&Huella={HUELLA_CASO_2}"
        "&FechaHoraHusoGenRegistro=2024-01-01T19:20:40+01:00"
    )
    assert cadena_anulacion(**CASO_3) == esperada


def test_cadena_completa_los_tres_casos_encadenan():
    """La secuencia alta -> alta -> anulacion forma una cadena valida."""
    h1 = huella_registro_alta(**CASO_1)
    h2 = huella_registro_alta(**dict(CASO_2, huella_anterior=h1))
    h3 = huella_registro_anulacion(**dict(CASO_3, huella_anterior=h2))
    assert (h1, h2, h3) == (HUELLA_CASO_1, HUELLA_CASO_2, HUELLA_CASO_3)


def test_trim_de_espacios_segun_spec():
    """
    Spec 0.1.2: los valores se toman 'eliminando los espacios al inicio y al
    final'. El ejemplo del documento: '   12345678 / G33  ' -> '12345678 / G33'
    (los espacios INTERIORES se conservan).
    """
    con_espacios = dict(CASO_1, num_serie_factura="   12345678/G33  ")
    assert huella_registro_alta(**con_espacios) == HUELLA_CASO_1
