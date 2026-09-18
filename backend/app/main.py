"""Punto de entrada del backend del Cotizador visual."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import obtener_configuracion
from app.db.cliente import crear_cliente
from app.routers import biblioteca, catalogo, cotizaciones, imagenes, salud


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    config = obtener_configuracion()
    app.state.supabase = await crear_cliente(config)
    yield


def crear_app() -> FastAPI:
    config = obtener_configuracion()
    app = FastAPI(
        title="Cotizador visual",
        version="0.1.0",
        description="API interna de Minimal 4.0 para armar propuestas visuales de mobiliario.",
        lifespan=ciclo_de_vida,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.lista_cors,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for router in (salud.router, cotizaciones.router, catalogo.router, imagenes.router, biblioteca.router):
        app.include_router(router, prefix="/api")
    return app


app = crear_app()
