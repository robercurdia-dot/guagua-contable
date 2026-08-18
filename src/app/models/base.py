"""Base declarativa SQLAlchemy 2.0 + mixin multi-tenant."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TenantMixin:
    """
    Aislamiento multi-tenant. Toda tabla de negocio lleva organizacion_id.
    En Postgres se refuerza con Row-Level Security (ver migrations/).
    """
    organizacion_id: Mapped[str] = mapped_column(String(36), index=True)
