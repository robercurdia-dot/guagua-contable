"""
Calculo de importes de la factura: bases, desglose de IVA, recargo de
equivalencia y totales.

POR QUE ESTO ES CRITICO: CuotaTotal e ImporteTotal entran literalmente en la
cadena de la huella Verifactu. Un redondeo de un centimo distinto produce una
huella distinta -> la AEAT marca el registro como "Aceptado con errores".

Criterio de redondeo (el habitual en la facturacion espanola y el que evita
acumular error):
  1. Base de cada linea = cantidad x precio, redondeada a 2 decimales.
  2. Las bases se AGRUPAN por (tipo de IVA, tipo de recargo)  -> desglose.
  3. La cuota se calcula sobre la base AGREGADA de cada grupo, no linea a linea.
  4. Todo con Decimal y ROUND_HALF_UP (nunca float: 0.1+0.2 != 0.3).
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

DOS_DECIMALES = Decimal("0.01")

# Tipos de IVA vigentes en Espana (%). 0 = exenta / no sujeta.
#
# LIMITACION CONOCIDA: la AEAT tambien admite tipos historicos/temporales
# (5%, 2%, 7.5% -- ver errores 1160, 1166, 1169 en schemas/errores.properties)
# para operaciones con fecha anterior. Esta tupla solo cubre los tipos vigentes,
# asi que el sistema NO puede facturar operaciones antiguas con esos tipos.
# Aceptable para el MVP (facturacion corriente); ampliar si hace falta emitir
# rectificativas de ejercicios con tipos temporales.
TIPOS_IVA_VIGENTES = (Decimal("21"), Decimal("10"), Decimal("4"), Decimal("0"))

# Recargo de equivalencia que corresponde a cada tipo de IVA (%).
#
# LIMITACION CONOCIDA (validado contra schemas/errores.properties):
#   - 1162: al 21% la AEAT admite 5,2 O BIEN 1,75 (este ultimo, labores del
#     tabaco). Aqui se asume siempre 5,2.
#   - 1170: al 0%, desde el 1-oct-2024 la AEAT solo admite 0,26, no 0. El valor
#     de abajo es incorrecto para el caso raro de 0% CON recargo.
# Ninguno de los dos casos se da en la facturacion corriente, pero hay que
# resolverlos antes de dar por cerrada la epica E2.
RECARGO_POR_TIPO = {
    Decimal("21"): Decimal("5.2"),
    Decimal("10"): Decimal("1.4"),
    Decimal("4"): Decimal("0.5"),
    Decimal("0"): Decimal("0"),
}


def redondear(valor) -> Decimal:
    """Redondeo monetario a 2 decimales, ROUND_HALF_UP (el fiscal en Espana)."""
    return Decimal(str(valor)).quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP)


def formatear(valor: Decimal) -> str:
    """Importe tal como se escribe en el registro y, por tanto, en la huella."""
    return f"{redondear(valor)}"


@dataclass(frozen=True)
class LineaCalculo:
    """Una linea de factura, en terminos de calculo."""
    descripcion: str
    cantidad: Decimal
    precio: Decimal
    tipo_iva: Decimal = Decimal("21")
    con_recargo: bool = False
    descuento_pct: Decimal = Decimal("0")

    def base(self) -> Decimal:
        """Base imponible de la linea (cantidad x precio - descuento), a 2 dec."""
        bruto = Decimal(str(self.cantidad)) * Decimal(str(self.precio))
        if self.descuento_pct:
            bruto = bruto * (Decimal("1") - Decimal(str(self.descuento_pct)) / Decimal("100"))
        return redondear(bruto)


@dataclass(frozen=True)
class DesgloseIVA:
    """Un grupo del desglose: todas las lineas con el mismo tipo de IVA/recargo."""
    tipo_iva: Decimal
    base: Decimal
    cuota: Decimal
    tipo_recargo: Decimal = Decimal("0")
    cuota_recargo: Decimal = Decimal("0")


@dataclass(frozen=True)
class TotalesFactura:
    base_imponible: Decimal
    cuota_iva: Decimal
    cuota_recargo: Decimal
    total: Decimal
    desglose: tuple[DesgloseIVA, ...] = field(default_factory=tuple)

    # --- valores tal como entran en la huella Verifactu ---
    @property
    def cuota_total_str(self) -> str:
        """CuotaTotal del registro: IVA + recargo de equivalencia."""
        return formatear(self.cuota_iva + self.cuota_recargo)

    @property
    def importe_total_str(self) -> str:
        """ImporteTotal del registro."""
        return formatear(self.total)


def calcular_factura(lineas: Iterable[LineaCalculo]) -> TotalesFactura:
    """
    Calcula bases, desglose por tipo de IVA y totales de una factura.

    Agrupa por (tipo_iva, con_recargo) y calcula la cuota sobre la base
    agregada de cada grupo -> evita acumular error de redondeo linea a linea.
    """
    lineas = list(lineas)
    for ln in lineas:
        tipo = Decimal(str(ln.tipo_iva))
        if tipo not in RECARGO_POR_TIPO:
            raise ValueError(
                f"Tipo de IVA no vigente: {tipo}%. Vigentes: "
                + ", ".join(f"{t}%" for t in TIPOS_IVA_VIGENTES)
            )
        if Decimal(str(ln.cantidad)) < 0:
            raise ValueError(f"Cantidad negativa en la linea '{ln.descripcion}'")

    # Agrupar bases por (tipo_iva, con_recargo)
    grupos: dict[tuple[Decimal, bool], Decimal] = {}
    for ln in lineas:
        clave = (Decimal(str(ln.tipo_iva)), ln.con_recargo)
        grupos[clave] = grupos.get(clave, Decimal("0")) + ln.base()

    desglose: list[DesgloseIVA] = []
    for (tipo_iva, con_recargo), base in sorted(
        grupos.items(), key=lambda kv: (-kv[0][0], kv[0][1])
    ):
        cuota = redondear(base * tipo_iva / Decimal("100"))
        tipo_recargo = RECARGO_POR_TIPO[tipo_iva] if con_recargo else Decimal("0")
        cuota_recargo = redondear(base * tipo_recargo / Decimal("100"))
        desglose.append(DesgloseIVA(
            tipo_iva=tipo_iva,
            base=redondear(base),
            cuota=cuota,
            tipo_recargo=tipo_recargo,
            cuota_recargo=cuota_recargo,
        ))

    base_total = redondear(sum((d.base for d in desglose), Decimal("0")))
    cuota_total = redondear(sum((d.cuota for d in desglose), Decimal("0")))
    recargo_total = redondear(sum((d.cuota_recargo for d in desglose), Decimal("0")))
    total = redondear(base_total + cuota_total + recargo_total)

    return TotalesFactura(
        base_imponible=base_total,
        cuota_iva=cuota_total,
        cuota_recargo=recargo_total,
        total=total,
        desglose=tuple(desglose),
    )
