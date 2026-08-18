"""
Autenticacion minima de la API.

ALCANCE: esto NO es el sistema de usuarios y roles para despachos (eso es el
resto de E5). Es solo no dejar la puerta abierta: una clave compartida por
cabecera, suficiente para entornos internos y de pruebas.

Cuando llegue el multiusuario real, esto se sustituye por sesiones/JWT con
identidad por usuario y el organizacion_id saldra del token, no de la peticion.
"""
from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from app.config import settings

CABECERA = "X-API-Key"


def requiere_api_key(x_api_key: str | None = Header(default=None, alias=CABECERA)) -> None:
    """
    Dependencia de FastAPI que exige la clave.

    Si no hay clave configurada, se BLOQUEA todo en lugar de dejar pasar: un
    despliegue al que se le olvide la variable de entorno debe quedarse mudo,
    no abierto de par en par.
    """
    esperada = settings.api_key
    if not esperada:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API sin clave configurada (API_KEY). Se bloquea por seguridad.",
        )
    # comparacion en tiempo constante: evita distinguir claves por lo que tardan
    if not x_api_key or not secrets.compare_digest(x_api_key, esperada):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Falta o es incorrecta la cabecera {CABECERA}",
            headers={"WWW-Authenticate": CABECERA},
        )
