"""Perfil del usuario autenticado (el frontend lo usa para saber el rol)."""

from fastapi import APIRouter

from app.auth import Usuario
from app.db.modelos import PerfilYo

router = APIRouter(prefix="/perfil", tags=["perfil"])


@router.get("/yo", response_model=PerfilYo)
async def perfil_actual(usuario: Usuario) -> PerfilYo:
    return PerfilYo(id=usuario.id, nombre=usuario.nombre, rol=usuario.rol, email=usuario.email)
