"""Gestión de usuarios (sólo admin): alta, rol, contraseña y baja, sin pasar por el dashboard."""

import re
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.auth import Usuario, UsuarioActual
from app.db.cliente import ClienteDB
from app.db.modelos import UsuarioActualizacion, UsuarioAdmin, UsuarioEntrada

router = APIRouter(prefix="/usuarios", tags=["usuarios"])

_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _exigir_admin(usuario: UsuarioActual) -> None:
    if not usuario.es_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sólo un administrador puede gestionar usuarios.")


def _fecha(valor: Any) -> datetime | None:
    if valor is None or isinstance(valor, datetime):
        return valor
    try:
        return datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError:
        return None


async def _usuarios_auth(db: Any) -> list[Any]:
    """Recorre todas las páginas de Supabase Auth."""
    usuarios: list[Any] = []
    pagina = 1
    while True:
        lote = await db.auth.admin.list_users(page=pagina, per_page=200)
        usuarios.extend(lote or [])
        if not lote or len(lote) < 200:
            return usuarios
        pagina += 1


async def _armar(db: Any, usuarios_auth: list[Any]) -> list[UsuarioAdmin]:
    perfiles = await db.table("perfiles").select("*").execute()
    por_id = {str(p["id"]): p for p in perfiles.data or []}
    resultado: list[UsuarioAdmin] = []
    for usuario in usuarios_auth:
        perfil = por_id.get(str(usuario.id), {})
        metadatos = getattr(usuario, "user_metadata", None) or {}
        resultado.append(
            UsuarioAdmin(
                id=usuario.id,
                email=usuario.email,
                nombre=perfil.get("nombre") or metadatos.get("nombre") or "",
                rol=perfil.get("rol") or "vendedor",
                creado_en=_fecha(getattr(usuario, "created_at", None)),
                ultimo_acceso=_fecha(getattr(usuario, "last_sign_in_at", None)),
            )
        )
    resultado.sort(key=lambda u: u.creado_en or datetime.min.replace(tzinfo=None), reverse=False)
    return resultado


@router.get("", response_model=list[UsuarioAdmin])
async def listar_usuarios(usuario: Usuario, db: ClienteDB) -> list[UsuarioAdmin]:
    _exigir_admin(usuario)
    return await _armar(db, await _usuarios_auth(db))


@router.post("", response_model=UsuarioAdmin, status_code=status.HTTP_201_CREATED)
async def crear_usuario(cuerpo: UsuarioEntrada, usuario: Usuario, db: ClienteDB) -> UsuarioAdmin:
    _exigir_admin(usuario)
    email = cuerpo.email.strip().lower()
    if not _CORREO.match(email):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "El correo no tiene un formato válido.")
    nombre = cuerpo.nombre.strip() or email.split("@")[0]
    try:
        creado = await db.auth.admin.create_user(
            {"email": email, "password": cuerpo.contrasena, "email_confirm": True, "user_metadata": {"nombre": nombre}}
        )
    except Exception as error:
        mensaje = str(error)
        if "already" in mensaje.lower() or "registered" in mensaje.lower():
            raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un usuario con ese correo.") from error
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Supabase Auth rechazó el alta: {mensaje}") from error
    nuevo = creado.user
    await db.table("perfiles").upsert({"id": str(nuevo.id), "nombre": nombre, "rol": cuerpo.rol}, on_conflict="id").execute()
    return (await _armar(db, [nuevo]))[0]


@router.patch("/{usuario_id}", response_model=UsuarioAdmin)
async def actualizar_usuario(usuario_id: UUID, cuerpo: UsuarioActualizacion, usuario: Usuario, db: ClienteDB) -> UsuarioAdmin:
    _exigir_admin(usuario)
    if cuerpo.rol == "vendedor" and str(usuario_id) == str(usuario.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "No puedes quitarte a ti mismo el rol de administrador.")

    try:
        actual = await db.auth.admin.get_user_by_id(str(usuario_id))
    except Exception as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El usuario no existe.") from error

    if cuerpo.contrasena:
        await db.auth.admin.update_user_by_id(str(usuario_id), {"password": cuerpo.contrasena})

    cambios_perfil = {k: v for k, v in {"nombre": cuerpo.nombre, "rol": cuerpo.rol}.items() if v is not None}
    if cambios_perfil:
        existente = await db.table("perfiles").select("id").eq("id", str(usuario_id)).limit(1).execute()
        if existente.data:
            await db.table("perfiles").update(cambios_perfil).eq("id", str(usuario_id)).execute()
        else:
            await db.table("perfiles").insert({"id": str(usuario_id), "nombre": cuerpo.nombre or "", "rol": cuerpo.rol or "vendedor"}).execute()

    return (await _armar(db, [actual.user]))[0]


@router.delete("/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_usuario(usuario_id: UUID, usuario: Usuario, db: ClienteDB) -> None:
    _exigir_admin(usuario)
    if str(usuario_id) == str(usuario.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "No puedes eliminar tu propia cuenta.")
    try:
        await db.auth.admin.delete_user(str(usuario_id))
    except Exception as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No se pudo eliminar el usuario: {error}") from error
