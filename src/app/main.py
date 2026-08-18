"""Punto de entrada FastAPI."""
from __future__ import annotations

from fastapi import FastAPI

from .api import facturas, health
from .config import settings

app = FastAPI(title=settings.app_name, version="0.1.0")
app.include_router(health.router)
app.include_router(facturas.router)


@app.get("/")
def root() -> dict:
    return {
        "producto": "Software de contabilidad y facturacion (Verifactu)",
        "fase": "0-1 (motor Verifactu validado + facturacion de venta)",
        "docs": "/docs",
    }
