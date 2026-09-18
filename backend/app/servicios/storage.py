"""Acceso a Supabase Storage: subir, descargar y firmar URLs.

Los buckets son privados. El frontend nunca recibe rutas públicas: sólo URLs firmadas de
corta duración (`URL_FIRMADA_SEGUNDOS`, 10 minutos por defecto).
"""

import mimetypes
import re
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from supabase import AsyncClient

from app.config import Configuracion, obtener_configuracion

_EXTENSIONES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}


def extension_por_tipo(content_type: str | None, nombre: str | None = None) -> str:
    if content_type in _EXTENSIONES:
        return _EXTENSIONES[content_type]
    if nombre:
        adivinado, _ = mimetypes.guess_type(nombre)
        if adivinado in _EXTENSIONES:
            return _EXTENSIONES[adivinado]
    return ".bin"


def nombre_seguro(nombre: str | None, por_defecto: str = "archivo") -> str:
    """Quita caracteres problemáticos para usarlos en rutas de Storage."""
    base = (nombre or por_defecto).strip().replace(" ", "_")
    base = re.sub(r"[^A-Za-z0-9._-]", "", base)
    return base or por_defecto


class Storage:
    def __init__(self, cliente: AsyncClient, config: Configuracion):
        self._cliente = cliente
        self._config = config

    @property
    def bucket_imagenes(self) -> str:
        return self._config.bucket_imagenes

    @property
    def bucket_exports(self) -> str:
        return self._config.bucket_exports

    async def subir(
        self, bucket: str, ruta: str, datos: bytes, content_type: str, sobrescribir: bool = False
    ) -> str:
        try:
            await self._cliente.storage.from_(bucket).upload(
                ruta,
                datos,
                {"content-type": content_type, "upsert": "true" if sobrescribir else "false"},
            )
        except Exception as error:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY, f"No se pudo guardar el archivo en Storage: {error}"
            ) from error
        return ruta

    async def descargar(self, bucket: str, ruta: str) -> bytes:
        try:
            return await self._cliente.storage.from_(bucket).download(ruta)
        except Exception as error:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY, f"No se pudo leer '{ruta}' de Storage: {error}"
            ) from error

    async def url_firmada(self, bucket: str, ruta: str, segundos: int | None = None) -> str:
        respuesta = await self._cliente.storage.from_(bucket).create_signed_url(
            ruta, segundos or self._config.url_firmada_segundos
        )
        return _extraer_url(respuesta)

    async def urls_firmadas(self, bucket: str, rutas: list[str]) -> dict[str, str]:
        """Firma varias rutas en una sola llamada. Las que fallen simplemente no aparecen."""
        unicas = sorted({r for r in rutas if r})
        if not unicas:
            return {}
        respuestas = await self._cliente.storage.from_(bucket).create_signed_urls(
            unicas, self._config.url_firmada_segundos
        )
        resultado: dict[str, str] = {}
        for respuesta in respuestas:
            url = _extraer_url(respuesta)
            ruta = respuesta.get("path") if isinstance(respuesta, dict) else None
            if url and ruta:
                resultado[str(ruta).lstrip("/")] = url
        return resultado


def _extraer_url(respuesta: object) -> str:
    if isinstance(respuesta, dict):
        return str(respuesta.get("signedURL") or respuesta.get("signedUrl") or "")
    return str(getattr(respuesta, "signed_url", "") or "")


def obtener_storage(
    request: Request, config: Annotated[Configuracion, Depends(obtener_configuracion)]
) -> Storage:
    return Storage(request.app.state.supabase, config)


StorageDep = Annotated[Storage, Depends(obtener_storage)]
