from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, _uuid


class Organizacion(Base, TimestampMixin):
    """El tenant. Un despacho puede gestionar N organizaciones."""
    __tablename__ = "organizacion"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    nif: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    razon_social: Mapped[str] = mapped_column(String(255))
    # modo Verifactu / No-Verifactu (ver app.verifactu.modos.ModoOperacion)
    modo_operacion: Mapped[str] = mapped_column(String(20), default="VERIFACTU")
