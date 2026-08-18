from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantMixin, TimestampMixin, _uuid


class RegistroFacturacion(Base, TimestampMixin, TenantMixin):
    """
    Registro de facturacion (alta / anulacion). Append-only: nunca se edita ni
    se borra; una factura se anula con un registro de anulacion encadenado.
    """
    __tablename__ = "registro_facturacion"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tipo: Mapped[str] = mapped_column(String(12))  # "alta" | "anulacion"
    factura_id: Mapped[str] = mapped_column(String(36), index=True)

    huella: Mapped[str] = mapped_column(String(64), index=True)
    huella_anterior: Mapped[str] = mapped_column(String(64), default="")
    fecha_hora_huso: Mapped[str] = mapped_column(String(40))

    xml: Mapped[str] = mapped_column(Text, default="")
    estado_aeat: Mapped[str] = mapped_column(String(24), default="pendiente")
    respuesta_aeat: Mapped[dict] = mapped_column(JSON, default=dict)


class EventoSIF(Base, TimestampMixin, TenantMixin):
    """Registro de eventos del SIF (arranque, parada, anomalias, exportaciones)."""
    __tablename__ = "evento_sif"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tipo_evento: Mapped[str] = mapped_column(String(40))
    detalle: Mapped[str] = mapped_column(Text, default="")
    ocurrido_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
