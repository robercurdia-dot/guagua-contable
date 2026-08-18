"""
Catalogo de errores de la AEAT y su clasificacion por severidad.

Fuente: errores.properties (oficial AEAT, en schemas/). El fichero se divide en
tres secciones y ESA CLASIFICACION ES LO IMPORTANTE en operacion:

  RECHAZO_ENVIO    -> se rechaza el ENVIO COMPLETO (el lote entero no entra).
                      Hay que corregir y reenviar todo.
  RECHAZO_REGISTRO -> se rechaza ESA factura; el resto del lote puede entrar.
  SUBSANABLE       -> el registro SI se acepta y queda almacenado, pero con
                      errores que deben subsanarse despues ("Aceptado con
                      errores"). NO reenviar a ciegas: ya esta registrado.

Confundir el tercer caso con un fallo y reintentar genera duplicados (error
3000, "Registro de facturacion duplicado").
"""
from __future__ import annotations

import re
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

RUTA_ERRORES = Path(__file__).parent / "schemas" / "errores.properties"


class Severidad(StrEnum):
    RECHAZO_ENVIO = "rechazo_envio"
    RECHAZO_REGISTRO = "rechazo_registro"
    SUBSANABLE = "subsanable"


# Cabeceras de seccion del fichero oficial, en orden de aparicion.
_MARCAS = (
    ("rechazo del envío completo", Severidad.RECHAZO_ENVIO),
    ("rechazo de la factura", Severidad.RECHAZO_REGISTRO),
    ("aceptación del registro", Severidad.SUBSANABLE),
)

_LINEA = re.compile(r"^\s*(\d+)\s*=\s*(.+?)\s*$")


@lru_cache(maxsize=1)
def catalogo() -> dict[int, tuple[Severidad, str]]:
    """{codigo: (severidad, descripcion)} parseado del fichero oficial."""
    if not RUTA_ERRORES.exists():
        return {}
    resultado: dict[int, tuple[Severidad, str]] = {}
    severidad = Severidad.RECHAZO_ENVIO
    for linea in RUTA_ERRORES.read_text(encoding="utf-8", errors="replace").splitlines():
        bajo = linea.lower()
        if bajo.lstrip().startswith("***"):
            for marca, sev in _MARCAS:
                if marca in bajo:
                    severidad = sev
                    break
            continue
        m = _LINEA.match(linea)
        if m:
            resultado[int(m.group(1))] = (severidad, m.group(2))
    return resultado


def severidad(codigo: int) -> Severidad | None:
    entrada = catalogo().get(codigo)
    return entrada[0] if entrada else None


def descripcion(codigo: int) -> str:
    entrada = catalogo().get(codigo)
    return entrada[1] if entrada else f"Codigo de error desconocido: {codigo}"


def es_reintentable(codigo: int) -> bool:
    """
    Un registro SUBSANABLE ya esta almacenado en la AEAT: reintentarlo crearia
    un duplicado (3000). Solo tiene sentido reintentar lo que fue rechazado.
    """
    return severidad(codigo) in (Severidad.RECHAZO_ENVIO, Severidad.RECHAZO_REGISTRO)


# Codigos que conviene tener a mano por lo que implican.
CODIGO_DUPLICADO = 3000
CODIGO_HUELLA_INCORRECTA = 2000
CODIGO_XML_NO_CUMPLE_ESQUEMA = 4102
CODIGO_NO_ES_PRIMER_REGISTRO = 2007
