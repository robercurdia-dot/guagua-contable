"""
Tests del motor de calculo de la factura.

Estos importes acaban literalmente en la cadena de la huella Verifactu, asi que
un error de un centimo aqui es un incumplimiento legal, no un detalle visual.
"""
from decimal import Decimal

import pytest

from app.facturacion import (
    RECARGOS_ADMITIDOS,
    TIPOS_IVA_ADMITIDOS,
    LineaCalculo,
    calcular_factura,
    formatear_num_serie,
    recargo_por_defecto,
    redondear,
    siguiente_numero,
    validar_recargo,
)
from app.verifactu.xml import (
    MAX_DETALLES_DESGLOSE,
    DetalleDesglose,
    Encadenamiento,
    RegistroAltaXML,
    SistemaInformatico,
)

SIF_TEST = SistemaInformatico(
    nombre_razon="The Guagua Project SL", nif="B12345678",
    nombre_sistema="Guagua Contable", id_sistema="01",
    version="0.1.0", numero_instalacion="INST-001",
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


# --------------------------------- recargo: casos de errores.properties
def test_recargo_del_0_por_ciento_es_026_no_cero():
    """AEAT 1170: al 0%, desde el 1-oct-2024 el recargo es 0,26, no 0."""
    assert recargo_por_defecto(0) == Decimal("0.26")
    t = calcular_factura([L(1, 100, 0, con_recargo=True)])
    assert t.cuota_recargo == Decimal("0.26")


def test_21_por_ciento_admite_tambien_175():
    """AEAT 1162: al 21% se admite 5,2 o 1,75 (tabaco)."""
    assert validar_recargo(21, "1.75") == Decimal("1.75")
    t = calcular_factura([L(1, 100, 21, tipo_recargo=Decimal("1.75"))])
    assert t.cuota_recargo == Decimal("1.75")
    assert t.total == Decimal("122.75")


def test_recargo_no_admitido_para_ese_tipo_falla():
    with pytest.raises(ValueError, match="no admitido para IVA"):
        validar_recargo(10, "5.2")
    with pytest.raises(ValueError, match="no admitido para IVA"):
        calcular_factura([L(1, 100, 4, tipo_recargo=Decimal("5.2"))])


def test_tipos_historicos_se_admiten():
    """Hacen falta para rectificar facturas de ejercicios anteriores."""
    t = calcular_factura([L(1, 100, "5")])
    assert t.cuota_iva == Decimal("5.00")
    assert recargo_por_defecto("5") == Decimal("0.5")
    assert validar_recargo("5", "0.62") == Decimal("0.62")


def test_mismo_iva_con_recargos_distintos_son_grupos_separados():
    """21% al 5,2 y 21% al 1,75 no pueden mezclarse en el desglose."""
    t = calcular_factura([
        L(1, 100, 21, con_recargo=True),
        L(1, 100, 21, tipo_recargo=Decimal("1.75")),
    ])
    assert len(t.desglose) == 2
    assert {d.tipo_recargo for d in t.desglose} == {Decimal("5.2"), Decimal("1.75")}
    assert t.cuota_recargo == Decimal("6.95")  # 5.20 + 1.75


def test_tipo_recargo_implica_recargo_sin_flag():
    """Informar tipo_recargo basta; no hace falta con_recargo=True."""
    t = calcular_factura([L(1, 100, 21, tipo_recargo=Decimal("5.2"))])
    assert t.cuota_recargo == Decimal("5.20")


def test_tabla_de_recargos_cubre_todos_los_tipos_admitidos():
    assert set(RECARGOS_ADMITIDOS) == set(TIPOS_IVA_ADMITIDOS)


# ------------------------- limite del desglose (XSD maxOccurs="12")
def test_combinaciones_posibles_de_tipo_y_recargo_caben_en_el_desglose():
    """
    DesgloseType/DetalleDesglose tiene maxOccurs="12" en el XSD. Cada grupo del
    desglose es una combinacion (tipo de IVA, recargo aplicado), asi que hay que
    saber cuantas combinaciones distintas son posibles: si pudieran superar 12,
    una factura legitima seria irrepresentable y la AEAT la rechazaria por
    esquema (4102) antes de llegar a ninguna validacion de negocio.
    """
    # cada tipo puede ir sin recargo, o con cualquiera de sus recargos admitidos
    combinaciones = sum(1 + len(recs) for recs in RECARGOS_ADMITIDOS.values())
    # 7 tipos; 21% y 5% tienen 2 recargos, 0% tiene 2, el resto 1
    assert combinaciones == 17, f"combinaciones posibles: {combinaciones}"
    assert combinaciones > MAX_DETALLES_DESGLOSE, (
        "Si todas las combinaciones cupieran en el desglose, este test sobra"
    )


def test_desglose_dentro_del_limite_del_xsd():
    """12 grupos distintos: el maximo que admite el esquema."""
    lineas = [
        L(1, 100, "21"), L(1, 100, "21", con_recargo=True),
        L(1, 100, "21", tipo_recargo=Decimal("1.75")),
        L(1, 100, "10"), L(1, 100, "10", con_recargo=True),
        L(1, 100, "4"), L(1, 100, "4", con_recargo=True),
        L(1, 100, "0"), L(1, 100, "0", con_recargo=True),
        L(1, 100, "5"), L(1, 100, "5", con_recargo=True),
        L(1, 100, "2"),
    ]
    t = calcular_factura(lineas)
    assert len(t.desglose) == MAX_DETALLES_DESGLOSE


def test_desglose_que_excede_el_limite_del_xsd_se_detecta():
    """
    13 grupos distintos. El calculo los produce sin quejarse (es aritmetica
    correcta), pero el XML NO puede representarlos: quien tiene que cazarlo es
    la construccion del registro, no el calculo.
    """
    lineas = [
        L(1, 100, "21"), L(1, 100, "21", con_recargo=True),
        L(1, 100, "21", tipo_recargo=Decimal("1.75")),
        L(1, 100, "10"), L(1, 100, "10", con_recargo=True),
        L(1, 100, "4"), L(1, 100, "4", con_recargo=True),
        L(1, 100, "0"), L(1, 100, "0", con_recargo=True),
        L(1, 100, "5"), L(1, 100, "5", con_recargo=True),
        L(1, 100, "5", tipo_recargo=Decimal("0.62")),
        L(1, 100, "2"),
    ]
    t = calcular_factura(lineas)
    assert len(t.desglose) == 13 > MAX_DETALLES_DESGLOSE

    # y al pasarlo al XML, salta antes de enviar nada a la AEAT
    detalles = tuple(
        DetalleDesglose(base_imponible=str(d.base), tipo_impositivo=str(d.tipo_iva),
                        cuota_repercutida=str(d.cuota))
        for d in t.desglose
    )
    with pytest.raises(ValueError, match="entre 1 y 12"):
        RegistroAltaXML(
            id_emisor="B12345678", num_serie_factura="A/2026-0001",
            fecha_expedicion="15-01-2026", nombre_razon_emisor="X",
            tipo_factura="F2", descripcion_operacion="X",
            desglose=detalles, cuota_total="0.00", importe_total="0.00",
            encadenamiento=Encadenamiento(primer_registro=True),
            sistema_informatico=SIF_TEST,
            fecha_hora_huso="2026-01-15T10:30:00+01:00", huella="0" * 64,
        )


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
def test_tipo_iva_no_admitido_falla():
    with pytest.raises(ValueError, match="no admitido"):
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
