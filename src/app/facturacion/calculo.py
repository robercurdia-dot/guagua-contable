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

# ---------------------------------------------------------------- tipos
# Tipos de IVA (%). 0 = tipo cero / exenta.
TIPOS_IVA_VIGENTES = (Decimal("21"), Decimal("10"), Decimal("4"), Decimal("0"))

# Tipos temporales o historicos. Se ADMITEN (hacen falta para rectificar
# facturas de ejercicios en que estuvieron vigentes), pero la AEAT valida que
# la fecha caiga dentro de su ventana: si se usan fuera, responde 1194/1235/1236.
# Esa validacion por fecha NO se hace aqui a proposito: preferimos dejar pasar
# la rectificativa legitima y que la AEAT de un error preciso, antes que
# bloquearla desde el sistema.
TIPOS_IVA_HISTORICOS = (Decimal("7.5"), Decimal("5"), Decimal("2"))

TIPOS_IVA_ADMITIDOS = TIPOS_IVA_VIGENTES + TIPOS_IVA_HISTORICOS

# Recargo de equivalencia admitido para cada tipo de IVA (%).
# El PRIMER valor de cada tupla es el habitual y se usa por defecto.
#
# Verificado contra el catalogo oficial (schemas/errores.properties):
#   1162: al 21% -> 5,2 o 1,75   (1,75 = labores del tabaco)
#   1163: al 10% -> 1,4
#   1164: al  4% -> 0,5
#   1170: al  0% -> 0,26 desde el 1-oct-2024  (antes 0; ver 1165)
#   1160/1167/1168: al 5% -> 0,5 o 0,62 segun fecha
#   1166: al  2% -> 0,26   (1-oct-2024 a 31-dic-2024)
#   1169: al 7,5% -> 1     (1-oct-2024 a 31-dic-2024)
RECARGOS_ADMITIDOS: dict[Decimal, tuple[Decimal, ...]] = {
    Decimal("21"): (Decimal("5.2"), Decimal("1.75")),
    Decimal("10"): (Decimal("1.4"),),
    Decimal("4"): (Decimal("0.5"),),
    Decimal("0"): (Decimal("0.26"), Decimal("0")),
    Decimal("7.5"): (Decimal("1"),),
    Decimal("5"): (Decimal("0.5"), Decimal("0.62")),
    Decimal("2"): (Decimal("0.26"),),
}


def recargo_por_defecto(tipo_iva) -> Decimal:
    """Recargo de equivalencia habitual para un tipo de IVA."""
    tipo = Decimal(str(tipo_iva))
    if tipo not in RECARGOS_ADMITIDOS:
        raise ValueError(f"Tipo de IVA no admitido: {tipo}%")
    return RECARGOS_ADMITIDOS[tipo][0]


def validar_recargo(tipo_iva, tipo_recargo) -> Decimal:
    """
    Comprueba que el recargo es uno de los admitidos para ese tipo de IVA.
    Un recargo incoherente lo rechaza la AEAT (1162-1170, 1277).
    """
    tipo = Decimal(str(tipo_iva))
    rec = Decimal(str(tipo_recargo))
    admitidos = RECARGOS_ADMITIDOS.get(tipo)
    if admitidos is None:
        raise ValueError(f"Tipo de IVA no admitido: {tipo}%")
    if rec not in admitidos:
        permitidos = " o ".join(str(a) for a in admitidos)
        raise ValueError(
            f"Recargo de equivalencia {rec}% no admitido para IVA {tipo}%; "
            f"la AEAT solo acepta {permitidos}"
        )
    return rec


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
    # Recargo explicito. Si se deja en None y con_recargo=True, se aplica el
    # habitual del tipo. Hay que informarlo para los casos que no son el
    # habitual, p.ej. 1,75% al 21% en labores del tabaco (AEAT 1162).
    tipo_recargo: Decimal | None = None
    descuento_pct: Decimal = Decimal("0")

    @property
    def lleva_recargo(self) -> bool:
        return self.con_recargo or self.tipo_recargo is not None

    def recargo_aplicable(self) -> Decimal:
        """Recargo a aplicar a esta linea (0 si no lleva)."""
        if not self.lleva_recargo:
            return Decimal("0")
        if self.tipo_recargo is not None:
            return validar_recargo(self.tipo_iva, self.tipo_recargo)
        return recargo_por_defecto(self.tipo_iva)

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
        if tipo not in TIPOS_IVA_ADMITIDOS:
            raise ValueError(
                f"Tipo de IVA no admitido: {tipo}%. Vigentes: "
                + ", ".join(f"{t}%" for t in TIPOS_IVA_VIGENTES)
                + "; historicos: "
                + ", ".join(f"{t}%" for t in TIPOS_IVA_HISTORICOS)
            )
        ln.recargo_aplicable()  # valida la combinacion tipo/recargo
        if Decimal(str(ln.cantidad)) < 0:
            raise ValueError(f"Cantidad negativa en la linea '{ln.descripcion}'")

    # Agrupar bases por (tipo_iva, tipo_recargo_aplicado). El recargo forma
    # parte de la clave: dos lineas al 21% con recargos distintos (5,2 y 1,75)
    # son grupos separados del desglose.
    grupos: dict[tuple[Decimal, Decimal], Decimal] = {}
    for ln in lineas:
        clave = (Decimal(str(ln.tipo_iva)), ln.recargo_aplicable())
        grupos[clave] = grupos.get(clave, Decimal("0")) + ln.base()

    desglose: list[DesgloseIVA] = []
    for (tipo_iva, tipo_recargo), base in sorted(
        grupos.items(), key=lambda kv: (-kv[0][0], -kv[0][1])
    ):
        cuota = redondear(base * tipo_iva / Decimal("100"))
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
