"""Tests del catalogo oficial de errores de la AEAT."""
from app.verifactu.errores import (
    CODIGO_DUPLICADO,
    CODIGO_HUELLA_INCORRECTA,
    CODIGO_XML_NO_CUMPLE_ESQUEMA,
    Severidad,
    catalogo,
    descripcion,
    es_reintentable,
    severidad,
)


def test_catalogo_se_carga():
    assert len(catalogo()) > 200


def test_clasificacion_por_severidad():
    # 4102: el XML no cumple el esquema -> cae el envio entero
    assert severidad(CODIGO_XML_NO_CUMPLE_ESQUEMA) is Severidad.RECHAZO_ENVIO
    # 1106: tipo de factura no permitido -> cae esa factura
    assert severidad(1106) is Severidad.RECHAZO_REGISTRO
    # 2000: huella incorrecta -> se ACEPTA con errores, hay que subsanar
    assert severidad(CODIGO_HUELLA_INCORRECTA) is Severidad.SUBSANABLE


def test_subsanable_no_se_reintenta():
    """Reintentar un 'aceptado con errores' provoca un duplicado (3000)."""
    assert es_reintentable(CODIGO_HUELLA_INCORRECTA) is False
    assert es_reintentable(CODIGO_XML_NO_CUMPLE_ESQUEMA) is True
    assert es_reintentable(CODIGO_DUPLICADO) is True


def test_descripcion_de_codigo_conocido_y_desconocido():
    assert "esquema" in descripcion(CODIGO_XML_NO_CUMPLE_ESQUEMA).lower()
    assert "desconocido" in descripcion(999999).lower()
