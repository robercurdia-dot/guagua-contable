from app.verifactu.qr import URL_COTEJO_PRODUCCION, URL_COTEJO_PRUEBAS, url_qr


def test_url_qr_pruebas_contiene_parametros():
    u = url_qr(
        nif_emisor="B12345678",
        num_serie_factura="A/2026-0001",
        fecha_expedicion="15-01-2026",
        importe_total="121.00",
    )
    assert u.startswith(URL_COTEJO_PRUEBAS)
    assert "nif=B12345678" in u
    assert "importe=121.00" in u


def test_url_qr_produccion():
    u = url_qr(
        nif_emisor="B12345678",
        num_serie_factura="A/2026-0001",
        fecha_expedicion="15-01-2026",
        importe_total="121.00",
        produccion=True,
    )
    assert u.startswith(URL_COTEJO_PRODUCCION)
