"""Modos de operacion del SIF."""
from __future__ import annotations

from enum import StrEnum


class ModoOperacion(StrEnum):
    """
    VERIFACTU  -> los registros se remiten a la AEAT en tiempo casi real.
                  No exige firma electronica por registro (la AEAT los custodia).
                  Recomendado para el MVP.
    NO_VERIFACTU -> los registros se conservan localmente, firmados con XAdES,
                  a disposicion de inspeccion. Mas requisitos.
    """
    VERIFACTU = "VERIFACTU"
    NO_VERIFACTU = "NO_VERIFACTU"

    @property
    def requiere_firma(self) -> bool:
        return self is ModoOperacion.NO_VERIFACTU

    @property
    def remite_a_aeat(self) -> bool:
        return self is ModoOperacion.VERIFACTU
