"""
Serializacion de los registros de facturacion a XML contra los XSD OFICIALES
de la AEAT (epica E1).

Esquemas de referencia (en schemas/, descargados de la AEAT):
  - SuministroInformacion.xsd : RegistroAlta / RegistroAnulacion y tipos base
  - SuministroLR.xsd          : envoltorio RegFactuSistemaFacturacion
  - RespuestaSuministro.xsd   : respuesta del servicio

REGLA DE ORO: el ORDEN de los elementos lo fija el XSD (son <sequence>), no
nuestra conveniencia. Si se reordena, el XML deja de validar. El orden de abajo
esta copiado literalmente de RegistroFacturacionAltaType / ...AnulacionType.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

SCHEMAS = Path(__file__).parent / "schemas"

NS_SF = "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/tike/cont/ws/SuministroInformacion.xsd"
NS_SFLR = "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/tike/cont/ws/SuministroLR.xsd"
NS_SFR = "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/tike/cont/ws/RespuestaSuministro.xsd"

NSMAP = {"sf": NS_SF, "sfLR": NS_SFLR}

ID_VERSION = "1.0"
TIPO_HUELLA_SHA256 = "01"

# Limite del XSD: DesgloseType/DetalleDesglose maxOccurs="12"
MAX_DETALLES_DESGLOSE = 12
# Limite del XSD: RegistroFactura maxOccurs="1000"
MAX_REGISTROS_POR_ENVIO = 1000


def _sf(tag: str) -> str:
    return f"{{{NS_SF}}}{tag}"


def _sflr(tag: str) -> str:
    return f"{{{NS_SFLR}}}{tag}"


def _sub(padre, tag: str, texto: str | None = None):
    el = etree.SubElement(padre, tag)
    if texto is not None:
        el.text = texto
    return el


# ---------------------------------------------------------------- datos
@dataclass(frozen=True)
class SistemaInformatico:
    """
    Bloque SistemaInformatico: identifica al SIF productor. Obligatorio.
    IdSistemaInformatico: max 2 caracteres. NumeroInstalacion: max 100.
    """
    nombre_razon: str
    nif: str
    nombre_sistema: str
    id_sistema: str
    version: str
    numero_instalacion: str
    solo_verifactu: str = "S"
    multi_ot: str = "N"
    indicador_multiples_ot: str = "N"

    def a_xml(self, padre, tag: str):
        el = _sub(padre, tag)
        _sub(el, _sf("NombreRazon"), self.nombre_razon)
        _sub(el, _sf("NIF"), self.nif)
        _sub(el, _sf("NombreSistemaInformatico"), self.nombre_sistema)
        _sub(el, _sf("IdSistemaInformatico"), self.id_sistema)
        _sub(el, _sf("Version"), self.version)
        _sub(el, _sf("NumeroInstalacion"), self.numero_instalacion)
        _sub(el, _sf("TipoUsoPosibleSoloVerifactu"), self.solo_verifactu)
        _sub(el, _sf("TipoUsoPosibleMultiOT"), self.multi_ot)
        _sub(el, _sf("IndicadorMultiplesOT"), self.indicador_multiples_ot)
        return el


@dataclass(frozen=True)
class Destinatario:
    nombre_razon: str
    nif: str


@dataclass(frozen=True)
class DetalleDesglose:
    """
    Una linea del desglose (DetalleType). Orden de campos fijado por el XSD.

    Reglas de la AEAT relevantes (ver errores.properties):
      - 1195: hay que informar CalificacionOperacion O OperacionExenta.
      - 1245: si Impuesto es IVA/IPSI/IGIC o va vacio, ClaveRegimen es obligatorio.
      - 1238: si la operacion es exenta NO se informan TipoImpositivo,
              CuotaRepercutida, TipoRecargoEquivalencia ni CuotaRecargoEquivalencia.
      - 1284: si se informa TipoRecargoEquivalencia hay que informar
              CuotaRecargoEquivalencia y viceversa.
    """
    base_imponible: str
    impuesto: str = "01"                      # 01 = IVA
    clave_regimen: str = "01"                 # 01 = regimen general
    calificacion_operacion: str | None = "S1"  # S1 = sujeta y no exenta
    operacion_exenta: str | None = None        # E1..E6 (excluyente con la anterior)
    tipo_impositivo: str | None = None
    cuota_repercutida: str | None = None
    tipo_recargo: str | None = None
    cuota_recargo: str | None = None

    def __post_init__(self):
        if bool(self.calificacion_operacion) == bool(self.operacion_exenta):
            raise ValueError(
                "Debe informarse CalificacionOperacion U OperacionExenta, "
                "exactamente uno de los dos (AEAT 1195/1196)"
            )
        if self.operacion_exenta and any(
            (self.tipo_impositivo, self.cuota_repercutida, self.tipo_recargo, self.cuota_recargo)
        ):
            raise ValueError(
                "Operacion exenta: no se informan TipoImpositivo, CuotaRepercutida "
                "ni recargo (AEAT 1238)"
            )
        if bool(self.tipo_recargo) != bool(self.cuota_recargo):
            raise ValueError(
                "TipoRecargoEquivalencia y CuotaRecargoEquivalencia van juntos (AEAT 1284)"
            )

    def a_xml(self, padre):
        el = _sub(padre, _sf("DetalleDesglose"))
        _sub(el, _sf("Impuesto"), self.impuesto)
        _sub(el, _sf("ClaveRegimen"), self.clave_regimen)
        if self.calificacion_operacion:
            _sub(el, _sf("CalificacionOperacion"), self.calificacion_operacion)
        else:
            _sub(el, _sf("OperacionExenta"), self.operacion_exenta)
        if self.tipo_impositivo is not None:
            _sub(el, _sf("TipoImpositivo"), self.tipo_impositivo)
        _sub(el, _sf("BaseImponibleOimporteNoSujeto"), self.base_imponible)
        if self.cuota_repercutida is not None:
            _sub(el, _sf("CuotaRepercutida"), self.cuota_repercutida)
        if self.tipo_recargo is not None:
            _sub(el, _sf("TipoRecargoEquivalencia"), self.tipo_recargo)
        if self.cuota_recargo is not None:
            _sub(el, _sf("CuotaRecargoEquivalencia"), self.cuota_recargo)
        return el


@dataclass(frozen=True)
class RegistroAnterior:
    """
    Identidad COMPLETA del registro anterior de la cadena.
    OJO: el XSD exige NIF + num/serie + fecha ademas de la huella; no basta
    con guardar la huella anterior.
    """
    id_emisor: str
    num_serie_factura: str
    fecha_expedicion: str
    huella: str


@dataclass(frozen=True)
class Encadenamiento:
    """
    CHOICE del XSD: o es el primer registro de la cadena, o referencia al
    anterior. No existe el caso 'huella anterior vacia' en el XML.
    """
    primer_registro: bool = False
    anterior: RegistroAnterior | None = None

    def __post_init__(self):
        if self.primer_registro == (self.anterior is not None):
            raise ValueError(
                "Encadenamiento: o PrimerRegistro o RegistroAnterior, "
                "exactamente uno de los dos"
            )

    def a_xml(self, padre):
        el = _sub(padre, _sf("Encadenamiento"))
        if self.primer_registro:
            _sub(el, _sf("PrimerRegistro"), "S")
        else:
            a = _sub(el, _sf("RegistroAnterior"))
            _sub(a, _sf("IDEmisorFactura"), self.anterior.id_emisor)
            _sub(a, _sf("NumSerieFactura"), self.anterior.num_serie_factura)
            _sub(a, _sf("FechaExpedicionFactura"), self.anterior.fecha_expedicion)
            _sub(a, _sf("Huella"), self.anterior.huella)
        return el


@dataclass(frozen=True)
class Cabecera:
    obligado_nombre: str
    obligado_nif: str
    representante_nombre: str | None = None
    representante_nif: str | None = None

    def a_xml(self, padre):
        el = _sub(padre, _sflr("Cabecera"))
        ob = _sub(el, _sf("ObligadoEmision"))
        _sub(ob, _sf("NombreRazon"), self.obligado_nombre)
        _sub(ob, _sf("NIF"), self.obligado_nif)
        if self.representante_nif:
            rp = _sub(el, _sf("Representante"))
            _sub(rp, _sf("NombreRazon"), self.representante_nombre)
            _sub(rp, _sf("NIF"), self.representante_nif)
        return el


@dataclass(frozen=True)
class RegistroAltaXML:
    """Registro de facturacion de alta, listo para serializar."""
    id_emisor: str
    num_serie_factura: str
    fecha_expedicion: str
    nombre_razon_emisor: str
    tipo_factura: str
    descripcion_operacion: str
    desglose: tuple[DetalleDesglose, ...]
    cuota_total: str
    importe_total: str
    encadenamiento: Encadenamiento
    sistema_informatico: SistemaInformatico
    fecha_hora_huso: str
    huella: str
    destinatarios: tuple[Destinatario, ...] = field(default_factory=tuple)

    def __post_init__(self):
        if not 1 <= len(self.desglose) <= MAX_DETALLES_DESGLOSE:
            raise ValueError(
                f"El desglose debe tener entre 1 y {MAX_DETALLES_DESGLOSE} lineas "
                f"(XSD DesgloseType/maxOccurs); recibidas {len(self.desglose)}"
            )
        # AEAT 1189/1190: F1/F3/R1-R4 exigen Destinatarios; F2/R5 no lo admiten.
        exige = self.tipo_factura in ("F1", "F3", "R1", "R2", "R3", "R4")
        if exige and not self.destinatarios:
            raise ValueError(
                f"TipoFactura {self.tipo_factura} exige el bloque Destinatarios (AEAT 1189)"
            )
        if not exige and self.destinatarios:
            raise ValueError(
                f"TipoFactura {self.tipo_factura} no admite Destinatarios (AEAT 1190)"
            )

    def a_xml(self, padre):
        """Orden literal de RegistroFacturacionAltaType (SuministroInformacion.xsd)."""
        el = _sub(padre, _sf("RegistroAlta"))
        _sub(el, _sf("IDVersion"), ID_VERSION)

        idf = _sub(el, _sf("IDFactura"))
        _sub(idf, _sf("IDEmisorFactura"), self.id_emisor)
        _sub(idf, _sf("NumSerieFactura"), self.num_serie_factura)
        _sub(idf, _sf("FechaExpedicionFactura"), self.fecha_expedicion)

        _sub(el, _sf("NombreRazonEmisor"), self.nombre_razon_emisor)
        _sub(el, _sf("TipoFactura"), self.tipo_factura)
        _sub(el, _sf("DescripcionOperacion"), self.descripcion_operacion)

        if self.destinatarios:
            dst = _sub(el, _sf("Destinatarios"))
            for d in self.destinatarios:
                idd = _sub(dst, _sf("IDDestinatario"))
                _sub(idd, _sf("NombreRazon"), d.nombre_razon)
                _sub(idd, _sf("NIF"), d.nif)

        desg = _sub(el, _sf("Desglose"))
        for det in self.desglose:
            det.a_xml(desg)

        _sub(el, _sf("CuotaTotal"), self.cuota_total)
        _sub(el, _sf("ImporteTotal"), self.importe_total)
        self.encadenamiento.a_xml(el)
        self.sistema_informatico.a_xml(el, _sf("SistemaInformatico"))
        _sub(el, _sf("FechaHoraHusoGenRegistro"), self.fecha_hora_huso)
        _sub(el, _sf("TipoHuella"), TIPO_HUELLA_SHA256)
        _sub(el, _sf("Huella"), self.huella)
        return el


@dataclass(frozen=True)
class RegistroAnulacionXML:
    id_emisor: str
    num_serie_factura: str
    fecha_expedicion: str
    encadenamiento: Encadenamiento
    sistema_informatico: SistemaInformatico
    fecha_hora_huso: str
    huella: str

    def a_xml(self, padre):
        """Orden literal de RegistroFacturacionAnulacionType."""
        el = _sub(padre, _sf("RegistroAnulacion"))
        _sub(el, _sf("IDVersion"), ID_VERSION)
        idf = _sub(el, _sf("IDFactura"))
        _sub(idf, _sf("IDEmisorFacturaAnulada"), self.id_emisor)
        _sub(idf, _sf("NumSerieFacturaAnulada"), self.num_serie_factura)
        _sub(idf, _sf("FechaExpedicionFacturaAnulada"), self.fecha_expedicion)
        self.encadenamiento.a_xml(el)
        self.sistema_informatico.a_xml(el, _sf("SistemaInformatico"))
        _sub(el, _sf("FechaHoraHusoGenRegistro"), self.fecha_hora_huso)
        _sub(el, _sf("TipoHuella"), TIPO_HUELLA_SHA256)
        _sub(el, _sf("Huella"), self.huella)
        return el


# ---------------------------------------------------------------- envio
def construir_envio(
    cabecera: Cabecera,
    registros: list[RegistroAltaXML | RegistroAnulacionXML],
) -> etree._Element:
    """Construye el RegFactuSistemaFacturacion completo (raiz del envio)."""
    if not registros:
        raise ValueError("El envio debe llevar al menos un registro")
    if len(registros) > MAX_REGISTROS_POR_ENVIO:
        raise ValueError(
            f"Maximo {MAX_REGISTROS_POR_ENVIO} registros por envio "
            f"(XSD RegistroFactura/maxOccurs); recibidos {len(registros)}"
        )
    raiz = etree.Element(_sflr("RegFactuSistemaFacturacion"), nsmap=NSMAP)
    cabecera.a_xml(raiz)
    for r in registros:
        rf = _sub(raiz, _sflr("RegistroFactura"))
        r.a_xml(rf)
    return raiz


def a_bytes(elemento: etree._Element) -> bytes:
    return etree.tostring(
        elemento, xml_declaration=True, encoding="UTF-8", pretty_print=True
    )


# ---------------------------------------------------------------- validacion
_esquema_cache: etree.XMLSchema | None = None


def esquema_suministro() -> etree.XMLSchema:
    """Compila (y cachea) el XSD oficial del envio."""
    global _esquema_cache
    if _esquema_cache is None:
        _esquema_cache = etree.XMLSchema(etree.parse(str(SCHEMAS / "SuministroLR.xsd")))
    return _esquema_cache


def validar(elemento: etree._Element) -> None:
    """
    Valida el XML contra el XSD oficial. Lanza ValueError con el detalle si no
    cumple. Es la ultima red antes de enviar a la AEAT: un XML invalido devuelve
    el error 4102 y se rechaza el envio COMPLETO.
    """
    esquema = esquema_suministro()
    if not esquema.validate(elemento):
        errores = "; ".join(f"linea {e.line}: {e.message}" for e in esquema.error_log)
        raise ValueError(f"El XML no cumple el XSD de la AEAT -> {errores}")
