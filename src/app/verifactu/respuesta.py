"""
Parseo e interpretacion de la respuesta del servicio de suministro.

Esquema: RespuestaSuministro.xsd (oficial AEAT).

LA SEMANTICA ES LO DELICADO DE ESTE MODULO. Hay dos niveles de estado y no
significan lo mismo:

  EstadoEnvio (del lote completo)
    Correcto              -> todos los registros entraron
    ParcialmenteCorrecto  -> algunos entraron y otros no; hay que mirar linea
                             a linea y reenviar SOLO los rechazados
    Incorrecto            -> no entro ninguno; corregir y reenviar todo

  EstadoRegistro (de cada registro)
    Correcto              -> almacenado
    AceptadoConErrores    -> ALMACENADO IGUALMENTE, con errores que hay que
                             subsanar. NO se reenvia: reenviarlo crea un
                             duplicado (error 3000)
    Incorrecto            -> rechazado; ese si se reenvia

Confundir "AceptadoConErrores" con un fallo es el error operativo mas caro que
se puede cometer aqui, porque genera duplicados en la AEAT.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field

from lxml import etree

from .errores import Severidad, descripcion, severidad

NS_SFR = "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/tike/cont/ws/RespuestaSuministro.xsd"
NS_SF = "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/tike/cont/ws/SuministroInformacion.xsd"
NS_SOAP = "http://schemas.xmlsoap.org/soap/envelope/"


class EstadoEnvio(enum.StrEnum):
    CORRECTO = "Correcto"
    PARCIAL = "ParcialmenteCorrecto"
    INCORRECTO = "Incorrecto"


class EstadoRegistro(enum.StrEnum):
    CORRECTO = "Correcto"
    ACEPTADO_CON_ERRORES = "AceptadoConErrores"
    INCORRECTO = "Incorrecto"


class ErrorSOAP(RuntimeError):
    """La AEAT devolvio un SOAP Fault (no una respuesta de negocio)."""


@dataclass(frozen=True)
class LineaRespuesta:
    num_serie_factura: str
    estado: EstadoRegistro
    codigo_error: int | None = None
    descripcion_error: str = ""
    duplicado_id_peticion: str | None = None

    @property
    def almacenado_en_aeat(self) -> bool:
        """
        True si el registro QUEDO guardado en la AEAT. Incluye el caso
        'aceptado con errores': esta dentro aunque haya que subsanarlo.
        """
        return self.estado in (
            EstadoRegistro.CORRECTO, EstadoRegistro.ACEPTADO_CON_ERRORES
        )

    @property
    def debe_reenviarse(self) -> bool:
        """Solo lo rechazado. Reenviar lo almacenado crea duplicados (3000)."""
        return self.estado is EstadoRegistro.INCORRECTO

    @property
    def necesita_subsanacion(self) -> bool:
        return self.estado is EstadoRegistro.ACEPTADO_CON_ERRORES

    @property
    def severidad_error(self) -> Severidad | None:
        return severidad(self.codigo_error) if self.codigo_error else None


@dataclass(frozen=True)
class Respuesta:
    estado_envio: EstadoEnvio
    lineas: tuple[LineaRespuesta, ...] = field(default_factory=tuple)
    csv: str | None = None
    tiempo_espera_envio: int | None = None   # segundos que pide esperar la AEAT
    nif_presentador: str | None = None

    @property
    def todo_correcto(self) -> bool:
        return self.estado_envio is EstadoEnvio.CORRECTO

    @property
    def envio_rechazado_entero(self) -> bool:
        return self.estado_envio is EstadoEnvio.INCORRECTO

    def a_reenviar(self) -> tuple[LineaRespuesta, ...]:
        """Registros que SI deben reintentarse."""
        return tuple(ln for ln in self.lineas if ln.debe_reenviarse)

    def a_subsanar(self) -> tuple[LineaRespuesta, ...]:
        """Almacenados pero con errores: se corrigen, no se reenvian."""
        return tuple(ln for ln in self.lineas if ln.necesita_subsanacion)


def _texto(nodo, tag: str, ns: str = NS_SFR) -> str | None:
    el = nodo.find(f"{{{ns}}}{tag}")
    return el.text if el is not None else None


def parsear(xml: bytes | etree._Element) -> Respuesta:
    """
    Parsea la respuesta del web service. Acepta el sobre SOAP completo o solo
    el cuerpo. Lanza ErrorSOAP si la AEAT devolvio un Fault.
    """
    raiz = etree.fromstring(xml) if isinstance(xml, bytes) else xml

    fault = raiz.find(f".//{{{NS_SOAP}}}Fault")
    if fault is not None:
        code = fault.findtext("faultcode") or "?"
        motivo = fault.findtext("faultstring") or "sin detalle"
        raise ErrorSOAP(f"SOAP Fault de la AEAT [{code}]: {motivo}")

    cuerpo = raiz.find(f".//{{{NS_SFR}}}RespuestaRegFactuSistemaFacturacion")
    if cuerpo is None:
        cuerpo = raiz  # ya venia sin sobre

    estado = _texto(cuerpo, "EstadoEnvio")
    if estado is None:
        raise ValueError("Respuesta sin EstadoEnvio: no es una respuesta valida de la AEAT")

    espera = _texto(cuerpo, "TiempoEsperaEnvio")
    presentacion = cuerpo.find(f"{{{NS_SF}}}DatosPresentacion")

    lineas = []
    for ln in cuerpo.findall(f"{{{NS_SFR}}}RespuestaLinea"):
        idf = ln.find(f"{{{NS_SF}}}IDFactura")
        num = idf.findtext(f"{{{NS_SF}}}NumSerieFactura") if idf is not None else ""
        cod = _texto(ln, "CodigoErrorRegistro")
        dup = ln.find(f"{{{NS_SF}}}RegistroDuplicado")
        desc = _texto(ln, "DescripcionErrorRegistro")
        codigo = int(cod) if cod else None
        lineas.append(LineaRespuesta(
            num_serie_factura=num or "",
            estado=EstadoRegistro(_texto(ln, "EstadoRegistro")),
            codigo_error=codigo,
            # si la AEAT no manda descripcion, se completa con el catalogo
            descripcion_error=desc or (descripcion(codigo) if codigo else ""),
            duplicado_id_peticion=(
                dup.findtext(f"{{{NS_SF}}}IdPeticionRegistroDuplicado")
                if dup is not None else None
            ),
        ))

    return Respuesta(
        estado_envio=EstadoEnvio(estado),
        lineas=tuple(lineas),
        csv=_texto(cuerpo, "CSV"),
        tiempo_espera_envio=int(espera) if espera else None,
        nif_presentador=(
            presentacion.findtext(f"{{{NS_SF}}}NIFPresentador")
            if presentacion is not None else None
        ),
    )
