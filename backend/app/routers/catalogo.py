"""Catálogo: búsqueda de ítems e imágenes de un ítem."""

import re
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.auth import Usuario
from app.db.cliente import ClienteDB
from app.db.modelos import CatalogoItem, Imagen
from app.servicios.storage import StorageDep

router = APIRouter(prefix="/catalogo", tags=["catalogo"])

_ORDEN_TIPO = {"oficial": 0, "variante": 1, "generada": 2}


def ordenar_imagenes(imagenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Oficial primero; después por usos (desc) y fecha (más reciente primero)."""
    return sorted(
        imagenes,
        key=lambda i: (_ORDEN_TIPO.get(i.get("tipo", ""), 9), -int(i.get("usos") or 0), str(i.get("creado_en", ""))),
    )


async def con_urls(storage: Any, imagenes: list[dict[str, Any]]) -> list[Imagen]:
    urls = await storage.urls_firmadas(storage.bucket_imagenes, [i["ruta_storage"] for i in imagenes])
    return [Imagen(**i, url=urls.get(i["ruta_storage"])) for i in imagenes]


@router.get("/items", response_model=list[CatalogoItem])
async def buscar_items(
    usuario: Usuario, db: ClienteDB, buscar: str = Query("", max_length=80), limite: int = Query(50, le=200)
) -> list[CatalogoItem]:
    """Búsqueda por código o nombre (sin distinguir mayúsculas)."""
    consulta = db.table("catalogo_items").select("*").order("codigo").limit(limite)
    termino = re.sub(r"[,()%*]", " ", buscar).strip()
    if termino:
        consulta = consulta.or_(f"codigo.ilike.*{termino}*,nombre.ilike.*{termino}*")
    respuesta = await consulta.execute()
    return [CatalogoItem(**i) for i in respuesta.data or []]


@router.get("/items/{item_id}/imagenes", response_model=list[Imagen])
async def imagenes_del_item(item_id: UUID, usuario: Usuario, db: ClienteDB, storage: StorageDep) -> list[Imagen]:
    item = await db.table("catalogo_items").select("id").eq("id", str(item_id)).limit(1).execute()
    if not item.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El ítem no existe.")
    respuesta = await db.table("imagenes").select("*").eq("item_id", str(item_id)).execute()
    return await con_urls(storage, ordenar_imagenes(respuesta.data or []))
