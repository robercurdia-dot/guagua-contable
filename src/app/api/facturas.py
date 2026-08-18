"""
API de emision de facturas (epica E2).

De momento SIN persistencia: calcula, numera y genera el registro Verifactu
encadenado. La persistencia y el envio a la AEAT entran con E5/E1.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.auth import requiere_api_key
from app.facturacion import (
    LineaCalculo,
    anular_factura,
    emitir_factura,
    verificar_libro,
)
from app.verifactu.huella import EslabonCadena
from app.verifactu.qr import LEYENDA_VERIFACTU, url_qr

router = APIRouter(
    prefix="/facturas",
    tags=["facturas"],
    dependencies=[Depends(requiere_api_key)],
)


class LineaIn(BaseModel):
    descripcion: str
    cantidad: Decimal = Decimal("1")
    precio: Decimal
    tipo_iva: Decimal = Decimal("21")
    con_recargo: bool = False
    tipo_recargo: Decimal | None = Field(
        None,
        description="Recargo de equivalencia explicito. Solo para casos que no "
                    "son el habitual del tipo (p.ej. 1.75 al 21%, tabaco).",
    )
    descuento_pct: Decimal = Decimal("0")


class EmitirIn(BaseModel):
    nif_emisor: str
    serie: str = "A/2026"
    ultimo_numero: int = Field(0, ge=0)
    fecha_expedicion: date
    generado_en: datetime = Field(
        ..., description="Fecha y hora CON huso horario (ej. 2026-01-15T10:30:00+01:00)"
    )
    tipo_factura: Literal["F1", "F2", "R1", "R2", "R3", "R4", "R5"] = "F1"
    huella_anterior: str = ""
    lineas: list[LineaIn]


class AnularIn(BaseModel):
    nif_emisor: str
    num_serie_factura: str
    fecha_expedicion: date
    generado_en: datetime
    huella_anterior: str


@router.post("/emitir")
def emitir(datos: EmitirIn) -> dict:
    """Emite una factura y devuelve su registro de facturacion de alta."""
    try:
        f = emitir_factura(
            nif_emisor=datos.nif_emisor,
            serie=datos.serie,
            ultimo_numero=datos.ultimo_numero,
            lineas=[LineaCalculo(**ln.model_dump()) for ln in datos.lineas],
            fecha_expedicion=datos.fecha_expedicion,
            generado_en=datos.generado_en,
            tipo_factura=datos.tipo_factura,
            huella_anterior=datos.huella_anterior,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    t = f.totales
    return {
        "factura": {
            "num_serie_factura": f.num_serie_factura,
            "numero": f.numero,
            "tipo_factura": f.tipo_factura,
            "fecha_expedicion": f.fecha_expedicion.isoformat(),
        },
        "importes": {
            "base_imponible": str(t.base_imponible),
            "cuota_iva": str(t.cuota_iva),
            "cuota_recargo": str(t.cuota_recargo),
            "total": str(t.total),
            "desglose": [
                {
                    "tipo_iva": str(d.tipo_iva),
                    "base": str(d.base),
                    "cuota": str(d.cuota),
                    "tipo_recargo": str(d.tipo_recargo),
                    "cuota_recargo": str(d.cuota_recargo),
                }
                for d in t.desglose
            ],
        },
        "registro_verifactu": {
            "tipo": "alta",
            "huella": f.huella,
            "huella_anterior": f.huella_anterior,
            "fecha_hora_huso": f.fecha_hora_huso,
            "cuota_total": t.cuota_total_str,
            "importe_total": t.importe_total_str,
        },
        "qr": {
            "url": url_qr(
                nif_emisor=f.nif_emisor,
                num_serie_factura=f.num_serie_factura,
                fecha_expedicion=f.fecha_expedicion.strftime("%d-%m-%Y"),
                importe_total=t.importe_total_str,
            ),
            "leyenda": LEYENDA_VERIFACTU,
            "aviso": "URL de cotejo pendiente de confirmar contra la spec oficial del QR",
        },
    }


@router.post("/anular")
def anular(datos: AnularIn) -> dict:
    """Genera el registro de anulacion de una factura ya emitida."""
    try:
        a = anular_factura(**datos.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return {
        "registro_verifactu": {
            "tipo": "anulacion",
            "num_serie_factura": a.num_serie_factura,
            "huella": a.huella,
            "huella_anterior": a.huella_anterior,
            "fecha_hora_huso": a.fecha_hora_huso,
        }
    }


class EslabonIn(BaseModel):
    huella: str
    huella_anterior: str


@router.post("/verificar-cadena")
def verificar(registros: list[EslabonIn]) -> dict:
    """Verifica la integridad del encadenamiento de un libro de registros."""
    integra = verificar_libro(
        [EslabonCadena(huella=r.huella, huella_anterior=r.huella_anterior) for r in registros]
    )
    return {"registros": len(registros), "cadena_integra": integra}
