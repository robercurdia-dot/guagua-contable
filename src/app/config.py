"""Configuracion de la app (pydantic-settings, 12-factor)."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "guagua-contable"
    entorno: str = "dev"  # dev | preprod | prod
    database_url: str = "postgresql+psycopg://guagua:guagua@localhost:5432/guagua"
    redis_url: str = "redis://localhost:6379/0"

    # Clave de la API. Vacia = la API se bloquea (no se abre) por seguridad.
    api_key: str = ""

    # Verifactu
    modo_verifactu_por_defecto: str = "VERIFACTU"
    aeat_entorno: str = "pruebas"  # pruebas | produccion


settings = Settings()
