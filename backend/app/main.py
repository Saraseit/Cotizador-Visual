"""Punto de entrada del backend del Cotizador visual."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import obtener_configuracion
from app.db.cliente import crear_cliente
from app.routers import biblioteca, catalogo, cotizaciones, imagenes, perfil, salud, usuarios

VERSION = "0.2.2"
registro = logging.getLogger("cotizador")


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    config = obtener_configuracion()
    app.state.supabase = await crear_cliente(config)
    if config.proveedor_efectivo != config.proveedor_imagenes:
        registro.warning(
            "OPENAI_API_KEY vacía: el proveedor de imágenes cae a 'simulado'. "
            "Define la llave en las variables del servicio para usar gpt-image-1."
        )
    registro.info("Entorno %s · proveedor de imágenes %s", config.entorno, config.proveedor_efectivo)
    yield


def crear_app() -> FastAPI:
    config = obtener_configuracion()
    origenes, regex_origenes = config.origenes_cors()  # en producción sin CORS_ORIGENES falla aquí, con mensaje claro
    app = FastAPI(
        title="Cotizador visual",
        version=VERSION,
        description="API interna de Minimal 4.0 para armar propuestas visuales de mobiliario.",
        lifespan=ciclo_de_vida,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origenes,
        allow_origin_regex=regex_origenes,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for router in (
        salud.router,
        perfil.router,
        cotizaciones.router,
        catalogo.router,
        imagenes.router,
        biblioteca.router,
        usuarios.router,
    ):
        app.include_router(router, prefix="/api")
    return app


app = crear_app()
