"""Cliente asíncrono de Supabase compartido por toda la aplicación.

Se usa la service role key: el backend ignora RLS y aplica las reglas de acceso en código
(ver `auth.py` y los routers). Nunca exponer esta llave al frontend.
"""

from typing import Annotated

from fastapi import Depends, Request
from supabase import AsyncClient, acreate_client

from app.config import Configuracion


async def crear_cliente(config: Configuracion) -> AsyncClient:
    return await acreate_client(config.supabase_url, config.supabase_service_role_key)


async def obtener_cliente(request: Request) -> AsyncClient:
    return request.app.state.supabase


ClienteDB = Annotated[AsyncClient, Depends(obtener_cliente)]
