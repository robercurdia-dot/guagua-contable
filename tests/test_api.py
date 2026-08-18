"""Tests de la API de facturacion."""
import pytest
from fastapi.testclient import TestClient

from app.api.auth import CABECERA
from app.config import settings

CLAVE = "clave-de-prueba"


@pytest.fixture(autouse=True)
def _con_clave(monkeypatch):
    monkeypatch.setattr(settings, "api_key", CLAVE)


@pytest.fixture
def c():
    from app.main import app
    cl = TestClient(app)
    cl.headers.update({CABECERA: CLAVE})
    return cl

FACTURA = {
    "nif_emisor": "B12345678",
    "serie": "A/2026",
    "ultimo_numero": 0,
    "fecha_expedicion": "2026-01-15",
    "generado_en": "2026-01-15T10:30:00+01:00",
    "lineas": [{"descripcion": "Consultoria", "cantidad": "10", "precio": "60"}],
}


def test_health(c):
    assert c.get("/health").json()["status"] == "ok"


def test_emitir_factura(c):
    r = c.post("/facturas/emitir", json=FACTURA)
    assert r.status_code == 200
    d = r.json()
    assert d["factura"]["num_serie_factura"] == "A/2026-0001"
    assert d["importes"]["total"] == "726.00"
    assert d["registro_verifactu"]["importe_total"] == "726.00"
    assert len(d["registro_verifactu"]["huella"]) == 64
    assert d["registro_verifactu"]["huella_anterior"] == ""


def test_emitir_encadena_con_anterior(c):
    h1 = c.post("/facturas/emitir", json=FACTURA).json()["registro_verifactu"]["huella"]
    segunda = dict(FACTURA, ultimo_numero=1, huella_anterior=h1)
    d2 = c.post("/facturas/emitir", json=segunda).json()
    assert d2["registro_verifactu"]["huella_anterior"] == h1
    assert d2["factura"]["num_serie_factura"] == "A/2026-0002"


def test_tipo_iva_invalido_devuelve_422(c):
    mala = dict(FACTURA, lineas=[{"descripcion": "x", "cantidad": "1",
                                  "precio": "100", "tipo_iva": "15"}])
    r = c.post("/facturas/emitir", json=mala)
    assert r.status_code == 422
    assert "no admitido" in r.json()["detail"]


def test_fecha_sin_huso_es_rechazada(c):
    mala = dict(FACTURA, generado_en="2026-01-15T10:30:00")
    r = c.post("/facturas/emitir", json=mala)
    assert r.status_code == 422


def test_anular_y_verificar_cadena(c):
    d1 = c.post("/facturas/emitir", json=FACTURA).json()
    h1 = d1["registro_verifactu"]["huella"]
    a = c.post("/facturas/anular", json={
        "nif_emisor": "B12345678",
        "num_serie_factura": "A/2026-0001",
        "fecha_expedicion": "2026-01-15",
        "generado_en": "2026-01-20T09:00:00+01:00",
        "huella_anterior": h1,
    }).json()["registro_verifactu"]

    v = c.post("/facturas/verificar-cadena", json=[
        {"huella": h1, "huella_anterior": ""},
        {"huella": a["huella"], "huella_anterior": a["huella_anterior"]},
    ]).json()
    assert v["cadena_integra"] is True


def test_cadena_rota_se_detecta_por_api(c):
    v = c.post("/facturas/verificar-cadena", json=[
        {"huella": "A" * 64, "huella_anterior": ""},
        {"huella": "B" * 64, "huella_anterior": "C" * 64},
    ]).json()
    assert v["cadena_integra"] is False


def test_anulacion_como_primer_registro_falla(c):
    r = c.post("/facturas/anular", json={
        "nif_emisor": "B12345678",
        "num_serie_factura": "A/2026-0001",
        "fecha_expedicion": "2026-01-15",
        "generado_en": "2026-01-20T09:00:00+01:00",
        "huella_anterior": "",
    })
    assert r.status_code == 422


# ------------------------------------------------------------ auth minima
def test_sin_clave_devuelve_401():
    from app.main import app
    sin = TestClient(app)
    assert sin.post("/facturas/emitir", json=FACTURA).status_code == 401


def test_clave_incorrecta_devuelve_401():
    from app.main import app
    mala = TestClient(app, headers={CABECERA: "no-es-esta"})
    assert mala.post("/facturas/emitir", json=FACTURA).status_code == 401


def test_health_no_exige_clave(c):
    from app.main import app
    assert TestClient(app).get("/health").status_code == 200


def test_sin_clave_configurada_la_api_se_bloquea(monkeypatch):
    """Un despliegue sin API_KEY debe quedarse mudo, no abierto."""
    from app.main import app
    monkeypatch.setattr(settings, "api_key", "")
    r = TestClient(app).post("/facturas/emitir", json=FACTURA)
    assert r.status_code == 503
    assert "bloquea" in r.json()["detail"]
