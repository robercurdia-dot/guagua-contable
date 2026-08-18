from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TenantMixin, TimestampMixin, _uuid


class Serie(Base, TimestampMixin, TenantMixin):
    __tablename__ = "serie"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    codigo: Mapped[str] = mapped_column(String(20))
    ultimo_numero: Mapped[int] = mapped_column(Integer, default=0)


class Cliente(Base, TimestampMixin, TenantMixin):
    __tablename__ = "cliente"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    nif: Mapped[str] = mapped_column(String(20), index=True)
    nombre: Mapped[str] = mapped_column(String(255))


class Producto(Base, TimestampMixin, TenantMixin):
    __tablename__ = "producto"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    descripcion: Mapped[str] = mapped_column(String(255))
    precio: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    tipo_iva: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=21)


class Factura(Base, TimestampMixin, TenantMixin):
    __tablename__ = "factura"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    serie_id: Mapped[str] = mapped_column(ForeignKey("serie.id"))
    numero: Mapped[int] = mapped_column(Integer)
    fecha_expedicion: Mapped[date] = mapped_column(Date)
    tipo_factura: Mapped[str] = mapped_column(String(4), default="F1")
    cliente_id: Mapped[str] = mapped_column(ForeignKey("cliente.id"))
    base_imponible: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    cuota_iva: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    estado: Mapped[str] = mapped_column(String(20), default="emitida")
    lineas: Mapped[list[LineaFactura]] = relationship(
        back_populates="factura", cascade="all, delete-orphan"
    )


class LineaFactura(Base, TimestampMixin, TenantMixin):
    __tablename__ = "linea_factura"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    factura_id: Mapped[str] = mapped_column(ForeignKey("factura.id"))
    descripcion: Mapped[str] = mapped_column(String(255))
    cantidad: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=1)
    precio: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    tipo_iva: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=21)
    factura: Mapped[Factura] = relationship(back_populates="lineas")
