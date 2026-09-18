"""Da de alta un usuario en Supabase Auth (correo + contraseña) y su perfil.

Uso:
  python scripts/crear_usuario.py --correo vendedor@empresa.com --contrasena "Secreta123!" --nombre "Ana" [--rol admin]

Idempotente: si el correo ya existe, sólo actualiza nombre y rol del perfil.
Necesita SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY en el .env de la raíz.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import obtener_configuracion  # noqa: E402
from app.db.cliente import crear_cliente  # noqa: E402


async def ejecutar(correo: str, contrasena: str, nombre: str, rol: str) -> None:
    db = await crear_cliente(obtener_configuracion())
    usuario_id: str | None = None

    try:
        respuesta = await db.auth.admin.create_user(
            {"email": correo, "password": contrasena, "email_confirm": True, "user_metadata": {"nombre": nombre}}
        )
        usuario_id = respuesta.user.id if respuesta.user else None
        print(f"Usuario creado: {correo}")
    except Exception as error:  # ya existe u otro error
        if "already" not in str(error).lower() and "registered" not in str(error).lower():
            raise
        pagina = await db.auth.admin.list_users(page=1, per_page=200)
        for usuario in pagina:
            if (usuario.email or "").lower() == correo.lower():
                usuario_id = usuario.id
                break
        if usuario_id is None:
            raise SystemExit(f"El correo {correo} ya existe pero no se pudo localizar su id.")
        await db.auth.admin.update_user_by_id(usuario_id, {"password": contrasena})
        print(f"Usuario ya existía, contraseña actualizada: {correo}")

    await db.table("perfiles").upsert({"id": usuario_id, "nombre": nombre, "rol": rol}, on_conflict="id").execute()
    print(f"Perfil listo: {nombre} ({rol}) · id {usuario_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--correo", required=True)
    parser.add_argument("--contrasena", required=True)
    parser.add_argument("--nombre", default="")
    parser.add_argument("--rol", choices=["vendedor", "admin"], default="vendedor")
    args = parser.parse_args()
    asyncio.run(ejecutar(args.correo, args.contrasena, args.nombre or args.correo.split("@")[0], args.rol))


if __name__ == "__main__":
    main()
