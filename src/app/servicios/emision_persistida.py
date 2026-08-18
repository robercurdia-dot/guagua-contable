"""
Emision de facturas con persistencia.

EL PROBLEMA QUE RESUELVE ESTE MODULO:

Emitir una factura no es solo calcular e insertar. Hay que, en un solo paso
indivisible:
  1. reservar el siguiente numero correlativo de la serie,
  2. leer la punta de la cadena Verifactu (el ultimo registro del SIF),
  3. calcular la huella encadenada a esa punta,
  4. insertar el registro y mover la punta.

Si dos emisiones concurrentes ejecutan (2) a la vez, ambas leen la misma punta
y producen dos registros que apuntan al mismo anterior: la cadena SE BIFURCA.
Eso es una anomalia de trazabilidad que el SIF esta obligado a detectar
(EventosSIF.xsd, tipos 04-08). Es preferible hacerla imposible.

COMO: se bloquea la fila de la organizacion con SELECT ... FOR UPDATE al
principio. Como la punta de la cadena vive en esa misma fila, el bloqueo
serializa toda la operacion. El candado es por ORGANIZACION, no por serie,
porque la cadena es unica por obligado/SIF aunque haya varias series.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.facturacion import LineaCalculo, emitir_factura, fecha_aeat
from app.models import Factura, LineaFactura, Organizacion, RegistroFacturacion
from app.verifactu.xml import RegistroAnterior


class EmisionError(RuntimeError):
    """Error de negocio al emitir (no de infraestructura)."""


@dataclass(frozen=True)
class ResultadoEmision:
    factura_id: str
    num_serie_factura: str
    numero: int
    huella: str
    huella_anterior: str
    registro_id: str


def _bloquear_organizacion(sesion: Session, organizacion_id: str) -> Organizacion:
    """
    Bloquea la fila de la organizacion hasta el fin de la transaccion.
    Es lo que serializa las emisiones y evita que la cadena se bifurque.
    """
    org = sesion.execute(
        text("SELECT id, nif, razon_social, cadena_huella, cadena_num_serie, "
             "       cadena_fecha_expedicion "
             "FROM organizacion WHERE id = :o FOR UPDATE"),
        {"o": organizacion_id},
    ).one_or_none()
    if org is None:
        raise EmisionError(f"Organizacion no encontrada: {organizacion_id}")
    return org


def emitir_y_registrar(
    sesion: Session,
    *,
    organizacion_id: str,
    serie_codigo: str,
    cliente_id: str,
    lineas: Sequence[LineaCalculo],
    fecha_expedicion: date,
    generado_en: datetime,
    tipo_factura: str = "F1",
) -> ResultadoEmision:
    """
    Emite una factura y persiste factura + lineas + registro de facturacion,
    todo dentro de la transaccion del llamante.
    """
    org = _bloquear_organizacion(sesion, organizacion_id)

    serie = sesion.execute(
        text("SELECT id, ultimo_numero FROM serie "
             "WHERE organizacion_id = :o AND codigo = :c"),
        {"o": organizacion_id, "c": serie_codigo},
    ).one_or_none()
    if serie is None:
        raise EmisionError(f"Serie no encontrada: {serie_codigo}")

    # Punta actual de la cadena (vacia si es el primer registro del SIF).
    anterior = None
    if org.cadena_huella:
        anterior = RegistroAnterior(
            id_emisor=org.nif,
            num_serie_factura=org.cadena_num_serie,
            fecha_expedicion=org.cadena_fecha_expedicion,
            huella=org.cadena_huella,
        )

    emitida = emitir_factura(
        nif_emisor=org.nif,
        serie=serie_codigo,
        ultimo_numero=serie.ultimo_numero,
        lineas=lineas,
        fecha_expedicion=fecha_expedicion,
        generado_en=generado_en,
        tipo_factura=tipo_factura,
        huella_anterior=org.cadena_huella,
        registro_anterior=anterior,
    )

    t = emitida.totales
    factura = Factura(
        organizacion_id=organizacion_id,
        serie_id=serie.id,
        numero=emitida.numero,
        fecha_expedicion=fecha_expedicion,
        tipo_factura=tipo_factura,
        cliente_id=cliente_id,
        base_imponible=t.base_imponible,
        cuota_iva=t.cuota_iva + t.cuota_recargo,
        total=t.total,
    )
    sesion.add(factura)
    sesion.flush()

    for ln in lineas:
        sesion.add(LineaFactura(
            organizacion_id=organizacion_id,
            factura_id=factura.id,
            descripcion=ln.descripcion,
            cantidad=Decimal(str(ln.cantidad)),
            precio=Decimal(str(ln.precio)),
            tipo_iva=Decimal(str(ln.tipo_iva)),
        ))

    registro = RegistroFacturacion(
        organizacion_id=organizacion_id,
        tipo="alta",
        factura_id=factura.id,
        huella=emitida.huella,
        huella_anterior=emitida.huella_anterior,
        fecha_hora_huso=emitida.fecha_hora_huso,
    )
    sesion.add(registro)

    # Avanzar el contador de la serie y la punta de la cadena.
    sesion.execute(
        text("UPDATE serie SET ultimo_numero = :n WHERE id = :i"),
        {"n": emitida.numero, "i": serie.id},
    )
    sesion.execute(
        text("UPDATE organizacion SET cadena_huella = :h, cadena_num_serie = :s, "
             "cadena_fecha_expedicion = :f WHERE id = :i"),
        {"h": emitida.huella, "s": emitida.num_serie_factura,
         "f": fecha_aeat(fecha_expedicion), "i": organizacion_id},
    )
    sesion.flush()

    return ResultadoEmision(
        factura_id=factura.id,
        num_serie_factura=emitida.num_serie_factura,
        numero=emitida.numero,
        huella=emitida.huella,
        huella_anterior=emitida.huella_anterior,
        registro_id=registro.id,
    )
