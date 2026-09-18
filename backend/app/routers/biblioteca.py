"""Métricas de la biblioteca de imágenes."""

from fastapi import APIRouter, Query

from app.auth import Usuario
from app.db.cliente import ClienteDB
from app.db.modelos import ResumenBiblioteca

router = APIRouter(prefix="/biblioteca", tags=["biblioteca"])


@router.get("/resumen", response_model=ResumenBiblioteca)
async def resumen(usuario: Usuario, db: ClienteDB, limite: int = Query(20, ge=1, le=200)) -> ResumenBiblioteca:
    """Calculado en la base con la función `resumen_biblioteca` (ver migraciones)."""
    respuesta = await db.rpc("resumen_biblioteca", {"limite_sin_imagen": limite}).execute()
    return ResumenBiblioteca(**(respuesta.data or {}))
