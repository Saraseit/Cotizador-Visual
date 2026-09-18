"""Render de la propuesta: datos -> HTML (Jinja2) -> PDF (WeasyPrint).

Las imágenes se incrustan como data URIs (reducidas a un tamaño razonable) para que
WeasyPrint no dependa de la red ni de URLs firmadas.
"""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.db.modelos import CotizacionDetalle

DIR_PLANTILLAS = Path(__file__).resolve().parent.parent / "plantillas"
PLANTILLA_PROPUESTA = "propuesta_base.html"
LADO_MAXIMO_MINIATURA = 640


@dataclass
class ItemRender:
    codigo: str
    descripcion: str
    cantidad: str
    precio_unitario: str
    importe: str
    imagen_data_uri: str | None
    es_render_conceptual: bool
    es_ad_hoc: bool


def formatear_moneda(valor: float | int) -> str:
    return f"${float(valor):,.2f}"


def formatear_cantidad(valor: float | int) -> str:
    numero = float(valor)
    return str(int(numero)) if numero.is_integer() else f"{numero:,.2f}"


def _entorno() -> Environment:
    entorno = Environment(
        loader=FileSystemLoader(DIR_PLANTILLAS),
        autoescape=select_autoescape(["html", "xml"]),
    )
    entorno.filters["moneda"] = formatear_moneda
    entorno.filters["cantidad"] = formatear_cantidad
    return entorno


def reducir_imagen(datos: bytes, lado_maximo: int = LADO_MAXIMO_MINIATURA) -> tuple[bytes, str]:
    """Reduce la imagen para el PDF. Devuelve (bytes, mime). Conserva transparencia como PNG."""
    from PIL import Image

    imagen = Image.open(BytesIO(datos))
    imagen.thumbnail((lado_maximo, lado_maximo))
    buffer = BytesIO()
    if imagen.mode in ("RGBA", "LA", "P"):
        imagen.convert("RGBA").save(buffer, format="PNG", optimize=True)
        return buffer.getvalue(), "image/png"
    imagen.convert("RGB").save(buffer, format="JPEG", quality=85, optimize=True)
    return buffer.getvalue(), "image/jpeg"


def a_data_uri(datos: bytes) -> str:
    reducida, mime = reducir_imagen(datos)
    return f"data:{mime};base64,{base64.b64encode(reducida).decode('ascii')}"


def construir_contexto(detalle: CotizacionDetalle, data_uris: dict[str, str]) -> dict[str, Any]:
    """`data_uris` va indexado por id de imagen (str)."""
    items = [
        ItemRender(
            codigo=item.codigo_origen,
            descripcion=item.descripcion_origen,
            cantidad=formatear_cantidad(item.cantidad),
            precio_unitario=formatear_moneda(item.precio_unitario),
            importe=formatear_moneda(item.importe),
            imagen_data_uri=data_uris.get(str(item.imagen_id)) if item.imagen_id else None,
            es_render_conceptual=item.es_render_conceptual,
            es_ad_hoc=item.tipo_item == "ad_hoc",
        )
        for item in detalle.items
    ]
    return {
        "nombre_cliente": detalle.nombre_cliente,
        "referencia_externa": detalle.referencia_externa,
        "fecha": datetime.now().strftime("%d/%m/%Y"),
        "items": items,
        "total": formatear_moneda(detalle.total),
        "hay_render_conceptual": any(i.es_render_conceptual for i in items),
        "total_items": len(items),
    }


def renderizar_html(contexto: dict[str, Any]) -> str:
    return _entorno().get_template(PLANTILLA_PROPUESTA).render(**contexto)


def html_a_pdf(html: str) -> bytes:
    try:
        from weasyprint import HTML
    except (ImportError, OSError) as error:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "WeasyPrint no está disponible en este servidor (faltan Pango/Cairo). "
            f"Detalle: {error}",
        ) from error
    return HTML(string=html, base_url=str(DIR_PLANTILLAS)).write_pdf()


async def generar_pdf_cotizacion(detalle: CotizacionDetalle, storage: Any) -> bytes:
    imagenes = {str(i.imagen.id): i.imagen.ruta_storage for i in detalle.items if i.imagen}

    async def descargar(imagen_id: str, ruta: str) -> tuple[str, str | None]:
        try:
            datos = await storage.descargar(storage.bucket_imagenes, ruta)
            return imagen_id, await asyncio.to_thread(a_data_uri, datos)
        except HTTPException:
            return imagen_id, None  # la imagen no está en Storage: se muestra "Sin imagen"

    resultados = await asyncio.gather(*(descargar(i, r) for i, r in imagenes.items()))
    data_uris = {imagen_id: uri for imagen_id, uri in resultados if uri}

    html = renderizar_html(construir_contexto(detalle, data_uris))
    return await asyncio.to_thread(html_a_pdf, html)
