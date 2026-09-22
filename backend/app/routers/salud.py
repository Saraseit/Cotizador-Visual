"""Diagnóstico del servicio: un renglón por dependencia con ok/detalle.

Devuelve 503 sólo si Supabase no responde (para que el healthcheck de Railway lo detecte).
Cualquier otra dependencia en rojo devuelve 200 con el detalle, así el servicio arranca y se
puede leer qué falta desde /api/salud o desde la pantalla /estado del frontend.
"""

from __future__ import annotations

import asyncio
import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.config import Configuracion, obtener_configuracion
from app.servicios.parser_export import CAMPOS_OBLIGATORIOS, ErrorParser, cargar_mapeo
from app.servicios.render_pdf import html_a_pdf

router = APIRouter(tags=["salud"])

_CACHE_WEASYPRINT: dict[str, Any] = {"hasta": 0.0, "resultado": None}
_VIDA_CACHE_WEASYPRINT = 300  # segundos; renderizar un PDF en cada ping sería un desperdicio


def _renglon(ok: bool, detalle: str) -> dict[str, Any]:
    return {"ok": ok, "detalle": detalle}


async def _verificar_supabase(db: Any) -> tuple[dict[str, Any], int | None]:
    try:
        respuesta = await db.table("perfiles").select("id", count="exact").limit(1).execute()
        usuarios = int(respuesta.count or 0)
        return _renglon(True, "Conexión y consulta a perfiles correctas"), usuarios
    except Exception as error:  # red, llave inválida, tabla inexistente
        return _renglon(False, f"No se pudo consultar Supabase: {str(error)[:200]}"), None


async def _verificar_buckets(db: Any, config: Configuracion) -> dict[str, Any]:
    try:
        buckets = await db.storage.list_buckets()
        nombres = {getattr(b, "name", None) or (b.get("name") if isinstance(b, dict) else None) for b in buckets}
    except Exception as error:
        return _renglon(False, f"No se pudieron listar los buckets: {str(error)[:200]}")
    faltan = [b for b in (config.bucket_imagenes, config.bucket_exports) if b not in nombres]
    if faltan:
        return _renglon(False, f"Faltan los buckets {faltan}; aplica la migración 20260918000002_rls_y_storage.sql")
    return _renglon(True, f"Buckets '{config.bucket_imagenes}' y '{config.bucket_exports}' presentes")


def _verificar_weasyprint_sincrono() -> dict[str, Any]:
    try:
        pdf = html_a_pdf("<html><body><p>Prueba de salud</p></body></html>")
    except Exception as error:
        detalle = getattr(error, "detail", None) or str(error)
        return _renglon(False, str(detalle)[:220])
    if not pdf.startswith(b"%PDF-"):
        return _renglon(False, "WeasyPrint respondió pero el resultado no es un PDF")
    return _renglon(True, f"PDF de prueba renderizado ({len(pdf)} bytes)")


async def _verificar_weasyprint() -> dict[str, Any]:
    ahora = time.monotonic()
    if _CACHE_WEASYPRINT["resultado"] is not None and ahora < _CACHE_WEASYPRINT["hasta"]:
        return _CACHE_WEASYPRINT["resultado"]
    resultado = await asyncio.to_thread(_verificar_weasyprint_sincrono)
    _CACHE_WEASYPRINT.update(hasta=ahora + _VIDA_CACHE_WEASYPRINT, resultado=resultado)
    return resultado


def _verificar_proveedor(config: Configuracion) -> dict[str, Any]:
    efectivo = config.proveedor_efectivo
    if efectivo == "openai":
        return _renglon(True, f"OpenAI ({config.openai_modelo_imagenes}, calidad {config.openai_calidad_imagenes}) con llave presente")
    if efectivo == "simulado":
        if config.proveedor_imagenes == "openai":
            return _renglon(True, "Simulado: OPENAI_API_KEY vacía, no se llama a ningún proveedor (define la llave para usar gpt-image-2.5)")
        return _renglon(True, "Simulado por configuración (PROVEEDOR_IMAGENES=simulado)")
    return _renglon(False, f"Proveedor desconocido '{efectivo}'; usa 'openai' o 'simulado'")


def _verificar_marca() -> dict[str, Any]:
    """La presentación editorial necesita los logos, las tipografías y su plantilla en la imagen."""
    from app.servicios import presentacion

    faltan = [
        str(ruta.relative_to(presentacion.APP))
        for ruta in (
            presentacion.DIR_MARCA / "logotipo.png",
            presentacion.DIR_MARCA / "monograma.png",
            presentacion.DIR_FUENTES / "PublicSans-Regular.ttf",
            presentacion.DIR_FUENTES / "BebasNeue-Regular.ttf",
            presentacion.DIR_PLANTILLAS / presentacion.PLANTILLA,
        )
        if not ruta.exists()
    ]
    if faltan:
        return _renglon(False, f"Faltan archivos de marca en la imagen: {', '.join(faltan)}")
    everett = sorted(presentacion.archivos_everett())
    detalle = f"Logos y tipografías presentes; títulos con Everett ({len(everett)} pesos)" if everett else (
        "Logos y tipografías presentes; sin los archivos de Everett, los títulos salen en Public Sans"
    )
    return _renglon(True, detalle)


def _verificar_mapeo(config: Configuracion) -> dict[str, Any]:
    try:
        mapeo = cargar_mapeo(config.ruta_mapeo_columnas)
    except (OSError, ValueError, ErrorParser) as error:
        return _renglon(False, f"No se pudo cargar {config.ruta_mapeo_columnas}: {str(error)[:160]}")
    columnas = ", ".join(f"{c}='{mapeo['columnas'][c]}'" for c in CAMPOS_OBLIGATORIOS)
    return _renglon(True, f"Mapeo cargado con los 4 campos obligatorios ({columnas})")


async def _contar_catalogo(db: Any) -> dict[str, Any]:
    try:
        respuesta = await db.table("catalogo_items").select("id", count="exact").limit(1).execute()
    except Exception as error:
        return _renglon(False, f"No se pudo contar el catálogo: {str(error)[:160]}")
    total = int(respuesta.count or 0)
    if total == 0:
        return _renglon(False, "Catálogo vacío: corre el seeding (scripts/arrancar.py o cargar_catalogo.py)")
    return _renglon(True, f"{total} ítems en el catálogo")


@router.get("/salud")
async def salud(request: Request, config: Annotated[Configuracion, Depends(obtener_configuracion)]) -> JSONResponse:
    db = getattr(request.app.state, "supabase", None)
    verificaciones: dict[str, dict[str, Any]] = {}

    if db is None:
        verificaciones["supabase"] = _renglon(False, "El cliente de Supabase no se inicializó")
        usuarios = None
    else:
        verificaciones["supabase"], usuarios = await _verificar_supabase(db)

    supabase_ok = verificaciones["supabase"]["ok"]
    if supabase_ok:
        verificaciones["buckets"] = await _verificar_buckets(db, config)
        verificaciones["catalogo"] = await _contar_catalogo(db)
        verificaciones["usuarios"] = (
            _renglon(True, f"{usuarios} usuarios con perfil")
            if usuarios
            else _renglon(False, "Sin usuarios: crea el primer admin con scripts/arrancar.py o crear_usuario.py")
        )
    else:
        no_evaluado = _renglon(False, "No evaluado: Supabase no responde")
        verificaciones["buckets"] = no_evaluado
        verificaciones["catalogo"] = no_evaluado
        verificaciones["usuarios"] = no_evaluado

    verificaciones["weasyprint"] = await _verificar_weasyprint()
    verificaciones["proveedor_imagenes"] = _verificar_proveedor(config)
    verificaciones["marca"] = _verificar_marca()
    verificaciones["mapeo_columnas"] = _verificar_mapeo(config)

    todo_ok = all(v["ok"] for v in verificaciones.values())
    cuerpo = {
        "estado": "ok" if todo_ok else ("caido" if not supabase_ok else "degradado"),
        "entorno": config.entorno,
        "version": request.app.version,
        "proveedor_imagenes": config.proveedor_efectivo,
        "verificaciones": verificaciones,
    }
    return JSONResponse(cuerpo, status_code=200 if supabase_ok else 503)
