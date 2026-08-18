"""
Huella / hash de los registros de facturacion y de evento (hash chain).

FUENTE DE VERDAD (implementado y validado contra este documento):
  AEAT — "Detalle de las especificaciones tecnicas para generacion de la huella
  o hash de los registros de facturacion", version 0.1.2 (27/08/2024).
  Art. 13 de la Orden HAC/1177/2024 que desarrolla el RD 1007/2023.

Algoritmo (verificado contra los 3 ejemplos oficiales, ver tests/test_huella.py):
  1. Se concatenan los campos, EN EL ORDEN de los disenos de registro oficiales,
     con la estructura:  nombreCampo1=valor1&nombreCampo2=valor2&...&nombreN=valorN
  2. Los valores se toman del XML eliminando espacios al inicio y al final.
     Si un campo no tiene valor, se pone el nombre y "=" sin valor
     (p.ej. el primer registro de la cadena: "...&Huella=&FechaHora...").
  3. La cadena se codifica en UTF-8.
  4. SHA-256. Salida en hexadecimal, MAYUSCULAS, 64 caracteres.

Nota sobre numericos (spec 0.1.2): en los campos de importe se tratan
indistintamente una o dos posiciones decimales; los ceros a la derecha no son
relevantes ("123.1" y "123.10" son ambos validos).

Si la huella informada no coincide con el calculo de la AEAT, el registro se
marca como "Aceptado con errores" -> por eso esto se valida contra los vectores
oficiales en CI.
"""
from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass

# Valor de la huella anterior cuando NO hay registro previo (primer registro).
# En la cadena aparece como "Huella=" (nombre del campo y "=" sin valor).
HUELLA_INICIAL = ""

# Orden EXACTO de campos (AEAT spec 0.1.2, apartado 3).
# No reordenar: el orden es el de los disenos de registro del anexo de la orden.
_CAMPOS_ALTA = (
    "IDEmisorFactura",
    "NumSerieFactura",
    "FechaExpedicionFactura",
    "TipoFactura",
    "CuotaTotal",
    "ImporteTotal",
    "Huella",                    # huella del registro ANTERIOR
    "FechaHoraHusoGenRegistro",
)

_CAMPOS_ANULACION = (
    "IDEmisorFacturaAnulada",
    "NumSerieFacturaAnulada",
    "FechaExpedicionFacturaAnulada",
    "Huella",                    # huella del registro ANTERIOR
    "FechaHoraHusoGenRegistro",
)

_CAMPOS_EVENTO = (
    "NIF",                       # SistemaInformatico/NIF
    "ID",                        # SistemaInformatico/IDOtro/ID (excluyente con NIF)
    "IdSistemaInformatico",
    "Version",
    "NumeroInstalacion",
    "NIFObligadoEmision",        # ObligadoEmision/NIF -> se serializa como "NIF"
    "TipoEvento",
    "HuellaEvento",              # huella del evento ANTERIOR
    "FechaHoraHusoGenEvento",
)

# El registro de evento tiene DOS campos que en el XML se llaman ambos "NIF"
# (SistemaInformatico/NIF y ObligadoEmision/NIF). En la cadena de la huella
# ambos aparecen con el nombre "NIF"; internamente los distinguimos.
_NOMBRE_EN_CADENA = {"NIFObligadoEmision": "NIF"}


def _normalizar(valor) -> str:
    """
    Valor tal como debe entrar en la cadena: sin espacios al inicio ni al final.
    None se trata como campo sin valor (cadena vacia).
    """
    if valor is None:
        return ""
    return str(valor).strip()


def _cadena_huella(campos: Sequence[str], valores: dict) -> str:
    """Construye 'campo=valor&campo=valor...' en el orden dado."""
    faltan = [c for c in campos if c not in valores]
    if faltan:
        raise ValueError(f"Faltan campos para la huella: {faltan}")
    partes = []
    for c in campos:
        nombre = _NOMBRE_EN_CADENA.get(c, c)
        partes.append(f"{nombre}={_normalizar(valores[c])}")
    return "&".join(partes)


def _sha256_hex_mayus(cadena: str) -> str:
    return hashlib.sha256(cadena.encode("utf-8")).hexdigest().upper()


def cadena_alta(
    *,
    id_emisor: str,
    num_serie_factura: str,
    fecha_expedicion: str,
    tipo_factura: str,
    cuota_total: str,
    importe_total: str,
    fecha_hora_huso: str,
    huella_anterior: str = HUELLA_INICIAL,
) -> str:
    """Cadena de entrada de la huella de un registro de ALTA (util para depurar)."""
    return _cadena_huella(_CAMPOS_ALTA, {
        "IDEmisorFactura": id_emisor,
        "NumSerieFactura": num_serie_factura,
        "FechaExpedicionFactura": fecha_expedicion,
        "TipoFactura": tipo_factura,
        "CuotaTotal": cuota_total,
        "ImporteTotal": importe_total,
        "Huella": huella_anterior,
        "FechaHoraHusoGenRegistro": fecha_hora_huso,
    })


def huella_registro_alta(**kwargs) -> str:
    """
    Huella de un registro de facturacion de ALTA.

    fecha_expedicion: formato AEAT dd-mm-aaaa
    fecha_hora_huso:  ISO 8601 con huso, p.ej. 2024-01-01T19:20:30+01:00
    huella_anterior:  huella del registro previo; "" si es el primero del SIF
    """
    return _sha256_hex_mayus(cadena_alta(**kwargs))


def cadena_anulacion(
    *,
    id_emisor: str,
    num_serie_factura: str,
    fecha_expedicion: str,
    fecha_hora_huso: str,
    huella_anterior: str = HUELLA_INICIAL,
) -> str:
    """Cadena de entrada de la huella de un registro de ANULACION."""
    return _cadena_huella(_CAMPOS_ANULACION, {
        "IDEmisorFacturaAnulada": id_emisor,
        "NumSerieFacturaAnulada": num_serie_factura,
        "FechaExpedicionFacturaAnulada": fecha_expedicion,
        "Huella": huella_anterior,
        "FechaHoraHusoGenRegistro": fecha_hora_huso,
    })


def huella_registro_anulacion(**kwargs) -> str:
    """Huella de un registro de facturacion de ANULACION."""
    return _sha256_hex_mayus(cadena_anulacion(**kwargs))


def huella_registro_evento(
    *,
    nif_sistema: str = "",
    id_otro: str = "",
    id_sistema_informatico: str,
    version: str,
    numero_instalacion: str,
    nif_obligado_emision: str,
    tipo_evento: str,
    fecha_hora_huso: str,
    huella_evento_anterior: str = HUELLA_INICIAL,
) -> str:
    """
    Huella de un REGISTRO DE EVENTO (obligatorio en sistemas NO VERI*FACTU).

    NIF e ID son excluyentes: se informa uno u otro; el que no se informe va
    como campo sin valor en la cadena.
    """
    cadena = _cadena_huella(_CAMPOS_EVENTO, {
        "NIF": nif_sistema,
        "ID": id_otro,
        "IdSistemaInformatico": id_sistema_informatico,
        "Version": version,
        "NumeroInstalacion": numero_instalacion,
        "NIFObligadoEmision": nif_obligado_emision,
        "TipoEvento": tipo_evento,
        "HuellaEvento": huella_evento_anterior,
        "FechaHoraHusoGenEvento": fecha_hora_huso,
    })
    return _sha256_hex_mayus(cadena)


@dataclass
class EslabonCadena:
    """Un registro dentro de la cadena, para verificacion de integridad."""
    huella: str
    huella_anterior: str


def verificar_cadena(eslabones: Sequence[EslabonCadena]) -> bool:
    """
    Verifica el encadenamiento: cada registro referencia la huella del
    inmediatamente anterior; el primero, HUELLA_INICIAL.
    """
    anterior = HUELLA_INICIAL
    for e in eslabones:
        if e.huella_anterior != anterior:
            return False
        anterior = e.huella
    return True
