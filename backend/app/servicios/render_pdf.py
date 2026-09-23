"""Render de la propuesta: datos -> HTML (Jinja2) -> PDF (WeasyPrint).

Las imágenes se incrustan como data URIs (reducidas a un tamaño razonable) para que
WeasyPrint no dependa de la red ni de URLs firmadas.
"""

from __future__ import annotations

import asyncio
import base64
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.db.modelos import ConfigPresentacion, CotizacionDetalle, descripcion_impresa
from app.servicios import idiomas

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


@dataclass
class Seccion:
    titulo: str  # '' = partidas sin sección (no lleva encabezado)
    items: list[ItemRender]


def agrupar_en_secciones(items: list[ItemRender], categorias: list[str]) -> list[Seccion]:
    """Agrupa partidas consecutivas con la misma sección, respetando el orden elegido."""
    secciones: list[Seccion] = []
    for item, categoria in zip(items, categorias):
        if not secciones or secciones[-1].titulo != categoria:
            secciones.append(Seccion(categoria, []))
        secciones[-1].items.append(item)
    return secciones


def construir_contexto(
    detalle: CotizacionDetalle, data_uris: dict[str, str], config: ConfigPresentacion | None = None
) -> dict[str, Any]:
    """`data_uris` va indexado por id de imagen (str).

    Las partidas de flete y montaje no se imprimen como renglón: se suman en el bloque de totales.
    `config` es la de la presentación de esta cotización: de ahí salen la moneda y el idioma, para que
    los dos PDF del cliente salgan iguales.
    """
    dinero = idiomas.Dinero(config.moneda, config.tipo_cambio) if config else idiomas.Dinero()
    traducir = idiomas.Traductor(config.idioma, dict(config.traducciones)) if config else idiomas.Traductor()
    t = idiomas.etiquetas_de(config.idioma if config else "es")
    partidas = [i for i in detalle.items if not i.cargo]
    items = [
        ItemRender(
            codigo=item.codigo_origen,
            descripcion=(
                descripcion_impresa(item)
                if (item.descripcion_editada or "").strip()
                else traducir(item.descripcion_origen)
            ),
            cantidad=formatear_cantidad(item.cantidad),
            precio_unitario=dinero(item.precio_unitario),
            importe=dinero(item.importe),
            imagen_data_uri=data_uris.get(str(item.imagen_id)) if item.imagen_id else None,
            es_render_conceptual=item.es_render_conceptual,
            es_ad_hoc=item.tipo_item == "ad_hoc",
        )
        for item in partidas
    ]
    totales: list[tuple[str, str]] = [(t["subtotal_mobiliario"], dinero(detalle.subtotal))]
    if any(i.cargo == "flete" for i in detalle.items):
        totales.append((t["flete"], dinero(detalle.flete)))
    if any(i.cargo == "montaje" for i in detalle.items):
        totales.append((t["montaje"], dinero(detalle.montaje)))
    if detalle.iva is not None:
        totales.append((t["iva"], dinero(detalle.iva)))
    ahora = datetime.now()
    fecha = ahora.strftime("%d/%m/%Y") if not config or config.idioma == "es" else ahora.strftime("%m/%d/%Y")
    return {
        "t": t,
        "idioma": config.idioma if config else "es",
        "nota_moneda": _nota_moneda(config, t, fecha),
        "nombre_cliente": detalle.nombre_cliente,
        "referencia_externa": detalle.referencia_externa,
        "fecha": fecha,
        "items": items,
        "secciones": agrupar_en_secciones(items, [traducir(i.categoria) for i in partidas]),
        "totales": totales,
        "total": dinero(detalle.total),
        "mas_iva": detalle.iva is None,
        "hay_render_conceptual": any(i.es_render_conceptual for i in items),
        "total_items": len(items),
    }


def _nota_moneda(config: ConfigPresentacion | None, t: dict[str, str], fecha: str) -> str:
    """Renglón al pie con la moneda de los importes (y el tipo de cambio si van en dólares)."""
    if config and config.moneda == "USD" and config.tipo_cambio:
        return t["precios_en_dolares"].format(tipo_cambio=f"{config.tipo_cambio:,.2f}", fecha=fecha)
    return t["precios_en_pesos"]


def renderizar_html(contexto: dict[str, Any]) -> str:
    return _entorno().get_template(PLANTILLA_PROPUESTA).render(**contexto)


_DIRECTORIOS_GTK_WINDOWS = (
    Path.home() / "AppData" / "Local" / "GTK3-Runtime" / "bin",
    Path("C:/Program Files/GTK3-Runtime Win64/bin"),
)


def _preparar_gtk_en_windows() -> None:
    """En Windows WeasyPrint necesita las DLL de GTK; si están en una ruta conocida se las indicamos."""
    if sys.platform != "win32" or os.environ.get("WEASYPRINT_DLL_DIRECTORIES"):
        return
    for directorio in _DIRECTORIOS_GTK_WINDOWS:
        if (directorio / "libgobject-2.0-0.dll").exists():
            os.environ["WEASYPRINT_DLL_DIRECTORIES"] = str(directorio)
            return


def html_a_pdf(html: str) -> bytes:
    _preparar_gtk_en_windows()
    try:
        from weasyprint import HTML
    except (ImportError, OSError) as error:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "WeasyPrint no está disponible en este servidor (faltan Pango/Cairo). "
            f"Detalle: {error}",
        ) from error
    return HTML(string=html, base_url=str(DIR_PLANTILLAS)).write_pdf()


async def generar_pdf_cotizacion(
    detalle: CotizacionDetalle, storage: Any, config: ConfigPresentacion | None = None
) -> bytes:
    imagenes = {str(i.imagen.id): i.imagen.ruta_storage for i in detalle.items if i.imagen and not i.cargo}

    async def descargar(imagen_id: str, ruta: str) -> tuple[str, str | None]:
        try:
            datos = await storage.descargar(storage.bucket_imagenes, ruta)
            return imagen_id, await asyncio.to_thread(a_data_uri, datos)
        except HTTPException:
            return imagen_id, None  # la imagen no está en Storage: se muestra "Sin imagen"

    resultados = await asyncio.gather(*(descargar(i, r) for i, r in imagenes.items()))
    data_uris = {imagen_id: uri for imagen_id, uri in resultados if uri}

    html = renderizar_html(construir_contexto(detalle, data_uris, config))
    return await asyncio.to_thread(html_a_pdf, html)
