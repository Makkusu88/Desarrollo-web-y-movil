import os
import threading
import time

import httpx


class SecretoNoDisponible(RuntimeError):


class SecretProvider:
    TTL_CACHE = 60          # segundos antes de volver a consultar Vault
    MAX_ANTIGUEDAD = 600    # si Vault cae, se usa la caché hasta este límite

    def __init__(self, servicio: str):
        self.servicio = servicio
        self.vault_addr = os.getenv("VAULT_ADDR", "http://127.0.0.1:8200")
        self._token = os.getenv("VAULT_TOKEN")
        if not self._token:
            raise RuntimeError(f"VAULT_TOKEN no configurado para el servicio {servicio}")
        self._ruta = f"{self.vault_addr}/v1/secret/data/mrsandwich/{servicio}"
        self._cache: dict | None = None
        self._leido_en = 0.0
        self._lock = threading.Lock()

    def _leer_vault(self) -> dict:
        resp = httpx.get(self._ruta, headers={"X-Vault-Token": self._token}, timeout=3.0)
        resp.raise_for_status()
        return resp.json()["data"]["data"]

    def todos(self) -> dict:
        with self._lock:
            ahora = time.monotonic()
            if self._cache is not None and ahora - self._leido_en < self.TTL_CACHE:
                return self._cache
            try:
                self._cache = self._leer_vault()
                self._leido_en = ahora
            except (httpx.HTTPError, KeyError) as exc:
                if self._cache is not None and ahora - self._leido_en < self.MAX_ANTIGUEDAD:
                    return self._cache
                raise SecretoNoDisponible("Gestor de secretos no disponible") from exc
            return self._cache

    def get(self, clave: str) -> str:
        valor = self.todos().get(clave)
        if valor is None:
            raise SecretoNoDisponible(f"Secreto '{clave}' no definido para {self.servicio}")
        return valor

    def opcional(self, clave: str) -> str | None:
        return self.todos().get(clave)
