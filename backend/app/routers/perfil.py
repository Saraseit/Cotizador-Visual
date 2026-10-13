"""Perfil del usuario autenticado: su rol y el cambio de su propia contraseña."""

import logging
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import Usuario
from app.config import Configuracion, obtener_configuracion
from app.db.cliente import ClienteDB
from app.db.modelos import CambioContrasena, PerfilYo

router = APIRouter(prefix="/perfil", tags=["perfil"])
registro = logging.getLogger("cotizador.perfil")

Config = Annotated[Configuracion, Depends(obtener_configuracion)]

TIEMPO_ESPERA = 30.0


@router.get("/yo", response_model=PerfilYo)
async def perfil_actual(usuario: Usuario) -> PerfilYo:
    return PerfilYo(id=usuario.id, nombre=usuario.nombre, rol=usuario.rol, email=usuario.email)


async def registrar_evento(db: Any, usuario_id: Any, tipo: str, detalle: str = "") -> None:
    """Deja el aviso para el administrador. Nunca tumba la operación del usuario si falla."""
    try:
        await db.table("eventos_cuenta").insert(
            {"usuario_id": str(usuario_id), "tipo": tipo, "detalle": detalle}
        ).execute()
    except Exception:
        registro.exception("No se pudo registrar el evento de cuenta '%s'", tipo)


async def _contrasena_es_correcta(config: Configuracion, correo: str, contrasena: str) -> bool:
    """Confirma la contraseña actual contra Supabase Auth, sin tocar la sesión del navegador."""
    url = f"{config.supabase_url.rstrip('/')}/auth/v1/token?grant_type=password"
    cabeceras = {"apikey": config.supabase_service_role_key, "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=TIEMPO_ESPERA) as cliente:
            respuesta = await cliente.post(url, headers=cabeceras, json={"email": correo, "password": contrasena})
    except httpx.HTTPError as error:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"No se pudo verificar la contraseña actual: {error}"
        ) from error
    return respuesta.status_code == 200


@router.post("/contrasena", status_code=status.HTTP_204_NO_CONTENT)
async def cambiar_contrasena(
    cuerpo: CambioContrasena, usuario: Usuario, db: ClienteDB, config: Config
) -> None:
    """Cambia la contraseña del propio usuario, confirmando antes la que tiene ahora.

    Cada cambio (y cada intento con la contraseña actual equivocada) queda registrado para que el
    administrador lo vea en la pantalla de Usuarios. No hace falta que el admin apruebe nada: eso
    dejaría a la persona sin acceso mientras espera.
    """
    if not usuario.email:
        raise HTTPException(status.HTTP_409_CONFLICT, "Tu cuenta no tiene correo; pide a un admin que la revise.")
    if cuerpo.contrasena_nueva == cuerpo.contrasena_actual:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "La contraseña nueva debe ser distinta de la actual.")

    if not await _contrasena_es_correcta(config, usuario.email, cuerpo.contrasena_actual):
        await registrar_evento(db, usuario.id, "intento_fallido", "Contraseña actual incorrecta al intentar cambiarla.")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "La contraseña actual no es correcta.")

    try:
        await db.auth.admin.update_user_by_id(str(usuario.id), {"password": cuerpo.contrasena_nueva})
    except Exception as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"No se pudo cambiar la contraseña: {error}") from error

    await registrar_evento(db, usuario.id, "cambio_contrasena", "Cambió su contraseña desde la aplicación.")
