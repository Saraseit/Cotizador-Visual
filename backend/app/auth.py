"""Validación del JWT de Supabase y resolución del perfil del usuario.

Soporta los dos esquemas de firma de Supabase:
  - HS256 con el JWT secret heredado (variable SUPABASE_JWT_SECRET).
  - Llaves asimétricas (ES256/RS256) publicadas en el endpoint JWKS del proyecto.

Al primer acceso de un usuario sin fila en `perfiles` se crea con rol 'vendedor'.
No hay registro: los usuarios se dan de alta en Supabase Auth.
"""

from functools import lru_cache
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.config import Configuracion, obtener_configuracion
from app.db.cliente import ClienteDB
from app.db.modelos import Perfil

esquema_bearer = HTTPBearer(auto_error=False)


class UsuarioActual(Perfil):
    email: str | None = None

    @property
    def es_admin(self) -> bool:
        return self.rol == "admin"


@lru_cache
def _cliente_jwks(url: str) -> PyJWKClient:
    return PyJWKClient(url, cache_keys=True, lifespan=3600)


def decodificar_token(token: str, config: Configuracion) -> dict[str, Any]:
    """Verifica firma, expiración y audiencia. Lanza jwt.PyJWTError si no es válido."""
    encabezado = jwt.get_unverified_header(token)
    algoritmo = encabezado.get("alg", "HS256")
    opciones = {"algorithms": [algoritmo], "audience": "authenticated"}

    if algoritmo.startswith("HS"):
        if not config.supabase_jwt_secret:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="El token usa HS256 pero falta SUPABASE_JWT_SECRET en la configuración.",
            )
        return jwt.decode(token, config.supabase_jwt_secret, **opciones)

    clave = _cliente_jwks(config.jwks_url).get_signing_key_from_jwt(token)
    return jwt.decode(token, clave.key, **opciones)


def _nombre_desde_claims(claims: dict[str, Any], email: str | None) -> str:
    metadatos = claims.get("user_metadata") or {}
    for llave in ("nombre", "name", "full_name"):
        if metadatos.get(llave):
            return str(metadatos[llave])
    return email.split("@")[0] if email else ""


async def usuario_actual(
    credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(esquema_bearer)],
    db: ClienteDB,
    config: Annotated[Configuracion, Depends(obtener_configuracion)],
) -> UsuarioActual:
    if credenciales is None or not credenciales.credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Se requiere iniciar sesión.")

    try:
        claims = decodificar_token(credenciales.credentials, config)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "La sesión expiró. Vuelve a entrar.")
    except jwt.PyJWTError as error:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Token inválido: {error}")

    usuario_id = claims.get("sub")
    if not usuario_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token sin identificador de usuario.")
    email = claims.get("email")

    respuesta = await db.table("perfiles").select("*").eq("id", usuario_id).limit(1).execute()
    if respuesta.data:
        perfil = respuesta.data[0]
    else:
        nuevo = {"id": usuario_id, "nombre": _nombre_desde_claims(claims, email), "rol": "vendedor"}
        creado = await db.table("perfiles").insert(nuevo).execute()
        perfil = creado.data[0] if creado.data else nuevo

    return UsuarioActual(id=perfil["id"], nombre=perfil.get("nombre", ""), rol=perfil.get("rol", "vendedor"), email=email)


Usuario = Annotated[UsuarioActual, Depends(usuario_actual)]
