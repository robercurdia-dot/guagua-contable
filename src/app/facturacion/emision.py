"""
Emision de facturas: une el dominio de facturacion con el motor Verifactu.

Flujo de una emision:
  1. Se calculan bases, desglose de IVA y totales (calculo.py).
  2. Se reserva el siguiente numero correlativo de la serie (numeracion.py).
  3. Se genera el REGISTRO DE ALTA con la huella encadenada a la del ultimo
     registro del SIF (verifactu/huella.py).
  4. (Pendiente E1) Se serializa a XML y se encola el envio a la AEAT.

La anulacion NO borra la factura: genera un registro de anulacion encadenado.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime

from app.verifactu.huella import (
    HUELLA_INICIAL,
    EslabonCadena,
    huella_registro_alta,
    huella_registro_anulacion,
    verificar_cadena,
)

from .calculo import LineaCalculo, TotalesFactura, calcular_factura
from .numeracion import formatear_num_serie, siguiente_numero


def fecha_aeat(f: date) -> str:
    """Formato de fecha de los registros AEAT: dd-mm-aaaa."""
    return f.strftime("%d-%m-%Y")


def fecha_hora_huso(dt: datetime) -> str:
    """
    FechaHoraHusoGenRegistro: ISO 8601 con huso horario.
    Ej: 2026-01-15T10:30:00+01:00. Exige datetime con tzinfo.
    """
    if dt.tzinfo is None:
        raise ValueError(
            "FechaHoraHusoGenRegistro exige fecha y hora con huso horario (tzinfo)"
        )
    return dt.isoformat(timespec="seconds")


@dataclass(frozen=True)
class FacturaEmitida:
    """Resultado de emitir una factura: la factura y su registro Verifactu."""
    serie: str
    numero: int
    num_serie_factura: str
    fecha_expedicion: date
    tipo_factura: str
    nif_emisor: str
    totales: TotalesFactura
    huella: str
    huella_anterior: str
    fecha_hora_huso: str

    @property
    def cadena_verifactu(self) -> EslabonCadena:
        return EslabonCadena(huella=self.huella, huella_anterior=self.huella_anterior)


def emitir_factura(
    *,
    nif_emisor: str,
    serie: str,
    ultimo_numero: int,
    lineas: Iterable[LineaCalculo],
    fecha_expedicion: date,
    generado_en: datetime,
    tipo_factura: str = "F1",
    huella_anterior: str = HUELLA_INICIAL,
) -> FacturaEmitida:
    """
    Emite una factura y genera su registro de facturacion de ALTA.

    huella_anterior: huella del ultimo registro del SIF ("" si es el primero).
    """
    totales = calcular_factura(lineas)
    numero = siguiente_numero(ultimo_numero)
    num_serie = formatear_num_serie(serie, numero)
    f_exp = fecha_aeat(fecha_expedicion)
    f_gen = fecha_hora_huso(generado_en)

    huella = huella_registro_alta(
        id_emisor=nif_emisor,
        num_serie_factura=num_serie,
        fecha_expedicion=f_exp,
        tipo_factura=tipo_factura,
        cuota_total=totales.cuota_total_str,
        importe_total=totales.importe_total_str,
        fecha_hora_huso=f_gen,
        huella_anterior=huella_anterior,
    )

    return FacturaEmitida(
        serie=serie,
        numero=numero,
        num_serie_factura=num_serie,
        fecha_expedicion=fecha_expedicion,
        tipo_factura=tipo_factura,
        nif_emisor=nif_emisor,
        totales=totales,
        huella=huella,
        huella_anterior=huella_anterior,
        fecha_hora_huso=f_gen,
    )


@dataclass(frozen=True)
class AnulacionEmitida:
    num_serie_factura: str
    huella: str
    huella_anterior: str
    fecha_hora_huso: str

    @property
    def cadena_verifactu(self) -> EslabonCadena:
        return EslabonCadena(huella=self.huella, huella_anterior=self.huella_anterior)


def anular_factura(
    *,
    nif_emisor: str,
    num_serie_factura: str,
    fecha_expedicion: date,
    generado_en: datetime,
    huella_anterior: str,
) -> AnulacionEmitida:
    """
    Genera el registro de ANULACION de una factura ya emitida.
    No borra nada: se encadena como un registro mas.
    """
    if not huella_anterior:
        raise ValueError(
            "Una anulacion nunca puede ser el primer registro del SIF: "
            "debe existir el registro de alta previo"
        )
    f_gen = fecha_hora_huso(generado_en)
    huella = huella_registro_anulacion(
        id_emisor=nif_emisor,
        num_serie_factura=num_serie_factura,
        fecha_expedicion=fecha_aeat(fecha_expedicion),
        fecha_hora_huso=f_gen,
        huella_anterior=huella_anterior,
    )
    return AnulacionEmitida(
        num_serie_factura=num_serie_factura,
        huella=huella,
        huella_anterior=huella_anterior,
        fecha_hora_huso=f_gen,
    )


def verificar_libro(registros: Sequence[EslabonCadena]) -> bool:
    """Verifica la integridad de la cadena completa de registros del SIF."""
    return verificar_cadena(registros)
