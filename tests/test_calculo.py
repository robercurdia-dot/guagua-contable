"""
Tests del motor de calculo de la factura.

Estos importes acaban literalmente en la cadena de la huella Verifactu, asi que
un error de un centimo aqui es un incumplimiento legal, no un detalle visual.
"""
from decimal import Decimal

import pytest

from app.facturacion import (
    LineaCalculo,
    calcular_factura,
    formatear_num_serie,
    redondear,
    siguiente_numero,
)


def L(cantidad, precio, tipo_iva="21", **kw):
    return LineaCalculo(
        descripcion="x",
        cantidad=Decimal(str(cantidad)),
        precio=Decimal(str(precio)),
        tipo_iva=Decimal(str(tipo_iva)),
        **kw,
    )


# ---------------------------------------------------------------- redondeo
def test_redondeo_es_half_up_no_bankers():
    """Python redondea 2.5 -> 2 por defecto (banker's). En fiscal debe ser 3."""
    assert redondear("2.345") == Decimal("2.35")
    assert redondear("2.355") == Decimal("2.36")
    assert redondear("0.005") == Decimal("0.01")   # banker's daria 0.00
    assert redondear("0.015") == Decimal("0.02")   # banker's daria 0.02
    assert redondear("0.025") == Decimal("0.03")   # banker's daria 0.02


def test_no_usa_float():
    """Con float, 0.1+0.2 = 0.30000000000000004. Con Decimal, no."""
    t = calcular_factura([L(1, "0.1", 0), L(1, "0.2", 0)])
    assert t.base_imponible == Decimal("0.30")


# ---------------------------------------------------------------- basico
def test_factura_simple_21():
    t = calcular_factura([L(1, 100)])
    assert t.base_imponible == Decimal("100.00")
    assert t.cuota_iva == Decimal("21.00")
    assert t.total == Decimal("121.00")
    assert t.cuota_total_str == "21.00"
    assert t.importe_total_str == "121.00"


def test_varias_lineas_mismo_tipo():
    t = calcular_factura([L(2, "10.50"), L(3, "5.25")])
    # 21.00 + 15.75 = 36.75 base ; 21% = 7.7175 -> 7.72
    assert t.base_imponible == Decimal("36.75")
    assert t.cuota_iva == Decimal("7.72")
    assert t.total == Decimal("44.47")


def test_desglose_por_tipos_distintos():
    t = calcular_factura([L(1, 100, 21), L(1, 100, 10), L(1, 100, 4)])
    assert t.base_imponible == Decimal("300.00")
    assert t.cuota_iva == Decimal("35.00")  # 21 + 10 + 4
    assert t.total == Decimal("335.00")
    assert len(t.desglose) == 3
    # ordenado de mayor a menor tipo
    assert [d.tipo_iva for d in t.desglose] == [Decimal("21"), Decimal("10"), Decimal("4")]


def test_cuota_se_calcula_sobre_base_agregada_no_linea_a_linea():
    """
    3 lineas de 0.10 al 21%.
    Linea a linea: round(0.021)=0.02 x3 = 0.06  <- INCORRECTO
    Sobre base agregada: 0.30 x 21% = 0.063 -> 0.06
    Con 10 lineas la diferencia se hace visible: ver test siguiente.
    """
    t = calcular_factura([L(1, "0.10") for _ in range(3)])
    assert t.base_imponible == Decimal("0.30")
    assert t.cuota_iva == Decimal("0.06")


def test_agregacion_evita_acumular_error():
    """10 lineas de 1.11 al 21%: agregado 11.10 x 21% = 2.331 -> 2.33.
    Linea a linea seria round(0.2331)=0.23 x10 = 2.30. Distinto."""
    t = calcular_factura([L(1, "1.11") for _ in range(10)])
    assert t.base_imponible == Decimal("11.10")
    assert t.cuota_iva == Decimal("2.33")
    assert t.total == Decimal("13.43")


# ---------------------------------------------------------------- exenta
def test_iva_cero_exenta():
    t = calcular_factura([L(1, 100, 0)])
    assert t.cuota_iva == Decimal("0.00")
    assert t.total == Decimal("100.00")


# ---------------------------------------------- recargo de equivalencia
def test_recargo_equivalencia_21():
    t = calcular_factura([L(1, 100, 21, con_recargo=True)])
    assert t.cuota_iva == Decimal("21.00")
    assert t.cuota_recargo == Decimal("5.20")
    assert t.total == Decimal("126.20")
    # CuotaTotal de la huella incluye IVA + recargo
    assert t.cuota_total_str == "26.20"


def test_recargo_por_tipo_correcto():
    for tipo, rec in ((10, "1.40"), (4, "0.50")):
        t = calcular_factura([L(1, 100, tipo, con_recargo=True)])
        assert t.cuota_recargo == Decimal(rec), f"tipo {tipo}"


def test_mismo_tipo_con_y_sin_recargo_son_grupos_distintos():
    t = calcular_factura([L(1, 100, 21), L(1, 100, 21, con_recargo=True)])
    assert len(t.desglose) == 2
    assert t.cuota_recargo == Decimal("5.20")


# ---------------------------------------------------------------- descuento
def test_descuento_en_linea():
    t = calcular_factura([L(1, 100, descuento_pct=Decimal("10"))])
    assert t.base_imponible == Decimal("90.00")
    assert t.cuota_iva == Decimal("18.90")


# ---------------------------------------------------------------- errores
def test_tipo_iva_no_vigente_falla():
    with pytest.raises(ValueError, match="no vigente"):
        calcular_factura([L(1, 100, 15)])


def test_cantidad_negativa_falla():
    with pytest.raises(ValueError, match="negativa"):
        calcular_factura([L(-1, 100)])


def test_factura_sin_lineas():
    t = calcular_factura([])
    assert t.base_imponible == Decimal("0.00")
    assert t.total == Decimal("0.00")
    assert t.importe_total_str == "0.00"


# ---------------------------------------------------------------- numeracion
def test_numeracion_correlativa():
    assert siguiente_numero(0) == 1
    assert siguiente_numero(41) == 42


def test_numeracion_negativa_falla():
    with pytest.raises(ValueError):
        siguiente_numero(-1)


def test_formato_num_serie():
    assert formatear_num_serie("A/2026", 1) == "A/2026-0001"
    assert formatear_num_serie("  FRA  ", 123) == "FRA-0123"
    assert formatear_num_serie("A", 12345) == "A-12345"  # no trunca


def test_formato_num_serie_invalido():
    with pytest.raises(ValueError):
        formatear_num_serie("", 1)
    with pytest.raises(ValueError):
        formatear_num_serie("A", 0)
