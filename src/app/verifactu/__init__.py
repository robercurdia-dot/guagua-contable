"""
Motor Verifactu — paquete aislado.

Implementa los requisitos del Sistema Informatico de Facturacion (SIF) segun:
  - Ley 11/2021 (antifraude)
  - Real Decreto 1007/2023 (reglamento SIF)
  - Orden HAC/1177/2024 (especificaciones tecnicas)

Este paquete NO depende de FastAPI, la base de datos ni el resto de la app:
se puede extraer a un servicio propio sin tocar nada mas.

El calculo de la huella esta VALIDADO contra los 3 vectores de ejemplo
oficiales de la AEAT (spec 0.1.2). Ver tests/test_huella.py.
"""

from .huella import (
    HUELLA_INICIAL,
    EslabonCadena,
    cadena_alta,
    cadena_anulacion,
    huella_registro_alta,
    huella_registro_anulacion,
    huella_registro_evento,
    verificar_cadena,
)
from .modos import ModoOperacion

__all__ = [
    "ModoOperacion",
    "HUELLA_INICIAL",
    "EslabonCadena",
    "cadena_alta",
    "cadena_anulacion",
    "huella_registro_alta",
    "huella_registro_anulacion",
    "huella_registro_evento",
    "verificar_cadena",
]
