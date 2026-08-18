from app.verifactu import HUELLA_INICIAL
from app.verifactu.registros import RegistroAlta, formatear_importe


def test_formatear_importe():
    assert formatear_importe(121) == "121.00"
    assert formatear_importe("121.005") == "121.01"  # ROUND_HALF_UP
    assert formatear_importe(0) == "0.00"


def test_registro_alta_calcula_huella():
    r = RegistroAlta(
        id_emisor="B12345678",
        num_serie_factura="A/2026-0001",
        fecha_expedicion="15-01-2026",
        tipo_factura="F1",
        cuota_total="21.00",
        importe_total="121.00",
        fecha_hora_huso="2026-01-15T10:30:00+01:00",
    )
    assert len(r.huella) == 64
    assert r.huella_anterior == HUELLA_INICIAL


def test_cadena_de_dos_registros():
    r1 = RegistroAlta(
        id_emisor="B12345678", num_serie_factura="A/2026-0001",
        fecha_expedicion="15-01-2026", tipo_factura="F1",
        cuota_total="21.00", importe_total="121.00",
        fecha_hora_huso="2026-01-15T10:30:00+01:00",
    )
    r2 = RegistroAlta(
        id_emisor="B12345678", num_serie_factura="A/2026-0002",
        fecha_expedicion="15-01-2026", tipo_factura="F1",
        cuota_total="10.00", importe_total="110.00",
        fecha_hora_huso="2026-01-15T10:35:00+01:00",
        huella_anterior=r1.huella,
    )
    assert r2.huella_anterior == r1.huella
    assert r1.huella != r2.huella
