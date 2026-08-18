"""
Construccion de registros de facturacion de alta y anulacion.

Un 'registro' es el objeto de negocio que luego se serializa a XML (contra el
XSD oficial de la AEAT) y del que se calcula la huella. Aqui se ensambla el
registro y se calcula su huella encadenada; la serializacion a XML se hara en
un modulo aparte (xml.py) contra el XSD, en la epica E1.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from .huella import (
    HUELLA_INICIAL,
    huella_registro_alta,
    huella_registro_anulacion,
)


def formatear_importe(valor) -> str:
    """
    Formatea un importe a 2 decimales con punto decimal, tal como debe aparecer
    en el registro y, por tanto, en la huella. Un formateo inconsistente rompe
    la cadena de hash.
    """
    d = Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{d}"


@dataclass
class RegistroAlta:
    id_emisor: str
    num_serie_factura: str
    fecha_expedicion: str            # dd-mm-aaaa
    tipo_factura: str
    cuota_total: str
    importe_total: str
    fecha_hora_huso: str
    huella_anterior: str = HUELLA_INICIAL
    huella: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.huella = huella_registro_alta(
            id_emisor=self.id_emisor,
            num_serie_factura=self.num_serie_factura,
            fecha_expedicion=self.fecha_expedicion,
            tipo_factura=self.tipo_factura,
            cuota_total=self.cuota_total,
            importe_total=self.importe_total,
            fecha_hora_huso=self.fecha_hora_huso,
            huella_anterior=self.huella_anterior,
        )


@dataclass
class RegistroAnulacion:
    id_emisor: str
    num_serie_factura: str
    fecha_expedicion: str
    fecha_hora_huso: str
    huella_anterior: str = HUELLA_INICIAL
    huella: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.huella = huella_registro_anulacion(
            id_emisor=self.id_emisor,
            num_serie_factura=self.num_serie_factura,
            fecha_expedicion=self.fecha_expedicion,
            fecha_hora_huso=self.fecha_hora_huso,
            huella_anterior=self.huella_anterior,
        )
