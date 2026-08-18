"""
Numeracion de facturas.

Requisito legal: la numeracion dentro de una serie debe ser CORRELATIVA y sin
huecos. El numero se reserva al emitir; no se reutiliza aunque la factura se
anule (la anulacion es otro registro, la factura sigue existiendo).
"""
from __future__ import annotations


def siguiente_numero(ultimo_numero: int) -> int:
    """Siguiente numero correlativo de la serie."""
    if ultimo_numero < 0:
        raise ValueError("El ultimo numero de serie no puede ser negativo")
    return ultimo_numero + 1


def formatear_num_serie(serie: str, numero: int, ancho: int = 4) -> str:
    """
    Construye el NumSerieFactura que va en el registro Verifactu.
    Ejemplo: serie='A/2026', numero=1 -> 'A/2026-0001'
    """
    serie = serie.strip()
    if not serie:
        raise ValueError("La serie no puede estar vacia")
    if numero <= 0:
        raise ValueError("El numero de factura debe ser positivo")
    return f"{serie}-{numero:0{ancho}d}"
