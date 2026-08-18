"""
Contexto multi-tenant.

Toda operacion se ejecuta dentro de una transaccion que fija
`app.organizacion_id`, que es lo que leen las politicas de Row-Level Security.

Se usa SET LOCAL a proposito: el valor muere con la transaccion, asi que una
conexion devuelta al pool no puede arrastrar el tenant de otra peticion.
"""
from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import text
from sqlalchemy.orm import Session


@contextmanager
def sesion_tenant(engine, organizacion_id: str):
    """Abre una sesion con el tenant fijado y la transaccion abierta."""
    if not organizacion_id:
        # Sin tenant las politicas RLS no dejan ver nada (falla en cerrado),
        # pero es mejor un error explicito que una consulta vacia inexplicable.
        raise ValueError("Se necesita organizacion_id para abrir la sesion")
    with Session(engine) as sesion:
        sesion.execute(
            text("SELECT set_config('app.organizacion_id', :org, true)"),
            {"org": organizacion_id},
        )
        yield sesion
        sesion.commit()
