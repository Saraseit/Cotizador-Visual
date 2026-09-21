"""Fotos de las partidas dentro del PDF de cotización del sistema.

El PDF trae la foto de cada artículo en la columna FOTOGRAFÍA, incrustada a su resolución original.
Cada foto empieza unos 3 pt arriba del renglón de su partida (medido en las cotizaciones 12066 y
12479), así que se empareja con la partida de la misma página cuyo `top` esté más cerca, dentro de
una tolerancia. El logo del encabezado queda lejos de cualquier renglón y no se empareja.

Se extrae el mapa de bits original (sin re-renderizar la página), se aplana a RGB, se reduce a un
lado máximo razonable y se guarda como JPEG. La huella (SHA-256 de los píxeles originales, no del
JPEG) sirve para no duplicar la misma foto cuando varias cotizaciones la traen.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from io import BytesIO
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.servicios.parser_export import FilaExport

registro = logging.getLogger("cotizador.fotos_pdf")

TOLERANCIA_PT = 15.0  # distancia máxima entre el borde superior de la foto y el renglón de la partida
LADO_MAXIMO_PX = 1600  # suficiente para la biblioteca y el PDF de propuesta; las originales llegan a 4000+ px
LADO_MINIMO_PX = 40  # íconos o adornos: no son fotos de producto
CALIDAD_JPEG = 88


@dataclass(frozen=True)
class FotoPartida:
    orden: int  # orden de la partida en el export
    datos: bytes  # JPEG normalizado
    huella: str  # sha256 hex de los píxeles originales (estable aunque cambie la compresión)
    ancho: int
    alto: int


def _normalizar(imagen) -> tuple[bytes, int, int]:
    from PIL import Image

    if imagen.mode in ("RGBA", "LA", "P"):
        con_alfa = imagen.convert("RGBA")
        fondo = Image.new("RGB", con_alfa.size, (255, 255, 255))
        fondo.paste(con_alfa, mask=con_alfa.split()[-1])
        imagen = fondo
    else:
        imagen = imagen.convert("RGB")
    imagen.thumbnail((LADO_MAXIMO_PX, LADO_MAXIMO_PX))
    buffer = BytesIO()
    imagen.save(buffer, format="JPEG", quality=CALIDAD_JPEG, optimize=True)
    return buffer.getvalue(), imagen.width, imagen.height


def extraer_fotos_partidas(contenido: bytes, filas: list[FilaExport]) -> dict[int, FotoPartida]:
    """Devuelve {orden de la partida: foto}. Nunca lanza: una foto que no se puede leer se omite."""
    import pypdfium2 as pdfium

    por_pagina: dict[int, list[FilaExport]] = {}
    for fila in filas:
        if fila.pagina is not None and fila.top is not None:
            por_pagina.setdefault(fila.pagina, []).append(fila)
    if not por_pagina:
        return {}

    fotos: dict[int, FotoPartida] = {}
    try:
        documento = pdfium.PdfDocument(contenido)
    except Exception as error:  # PDF que pdfplumber sí abrió pero pdfium no
        registro.warning("No se pudieron leer las fotos del PDF: %s", error)
        return {}

    try:
        for numero, filas_pagina in por_pagina.items():
            if numero >= len(documento):
                continue
            pagina = documento[numero]
            alto_pagina = pagina.get_height()
            candidatas = []
            for objeto in pagina.get_objects(filter=[pdfium.raw.FPDF_PAGEOBJ_IMAGE]):
                try:
                    _, _, _, arriba = objeto.get_bounds()
                    candidatas.append((alto_pagina - arriba, objeto))
                except Exception:
                    continue

            usadas: set[int] = set()
            for fila in filas_pagina:
                cercanas = [
                    (abs(top - fila.top), i, objeto)
                    for i, (top, objeto) in enumerate(candidatas)
                    if i not in usadas and abs(top - fila.top) <= TOLERANCIA_PT
                ]
                if not cercanas:
                    continue
                _, indice, objeto = min(cercanas, key=lambda c: c[0])
                try:
                    original = objeto.get_bitmap(render=False).to_pil()
                    if min(original.size) < LADO_MINIMO_PX:
                        continue
                    huella = hashlib.sha256(
                        f"{original.mode}:{original.width}x{original.height}:".encode() + original.tobytes()
                    ).hexdigest()
                    datos, ancho, alto = _normalizar(original)
                except Exception as error:
                    registro.warning("Foto de la partida %s ilegible: %s", fila.orden, error)
                    continue
                usadas.add(indice)
                fotos[fila.orden] = FotoPartida(fila.orden, datos, huella, ancho, alto)
    finally:
        documento.close()
    return fotos


# ---------------------------------------------------------------------------
# Guardado en la biblioteca
# ---------------------------------------------------------------------------

async def guardar_en_biblioteca(
    db,
    storage,
    filas: list[FilaExport],
    resultados: list,
    catalogo: dict[str, dict],
    imagenes_por_item: dict[str, list[dict]],
    fotos: dict[int, FotoPartida],
    usuario_id: str | None,
    referencia: str,
) -> tuple[int, dict[int, str]]:
    """Guarda en la biblioteca las fotos de las partidas y devuelve (fotos nuevas, {orden: imagen_id}).

    - Partida del catálogo: la foto va a la biblioteca de ese artículo. Si el artículo no tenía foto
      oficial, queda como oficial; si ya tenía, como variante.
    - Partida fuera de catálogo: la foto se guarda suelta (sin artículo) sólo para esa línea.
    - Una foto que ya está en la biblioteca (misma huella y mismo artículo) no se vuelve a subir.
    `imagenes_por_item` se actualiza en sitio para que el matching elija las fotos recién guardadas.
    """
    from app.servicios.storage import ruta_imagen_catalogo

    if not fotos:
        return 0, {}
    codigo_por_id = {str(item["id"]): item["codigo"] for item in catalogo.values()}
    huellas = sorted({f.huella for f in fotos.values()})
    previas = (await db.table("imagenes").select("*").in_("origen->>huella", huellas).execute()).data or []
    por_clave: dict[tuple[str | None, str], dict] = {
        (str(i["item_id"]) if i.get("item_id") else None, (i.get("origen") or {}).get("huella")): i for i in previas
    }

    nuevas = 0
    imagen_por_orden: dict[int, str] = {}
    for fila, resultado in zip(filas, resultados):
        foto = fotos.get(fila.orden)
        if foto is None:
            continue
        item_id = str(resultado.item_id) if resultado.item_id else None
        clave = (item_id, foto.huella)
        imagen = por_clave.get(clave)
        if imagen is None:
            codigo = codigo_por_id.get(item_id) if item_id else None
            ruta = ruta_imagen_catalogo(codigo, f"pdf-{foto.huella[:24]}.jpg", "" if item_id else "cotizaciones")
            await storage.subir(storage.bucket_imagenes, ruta, foto.datos, "image/jpeg", sobrescribir=True)
            tiene_oficial = any(i.get("tipo") == "oficial" for i in imagenes_por_item.get(item_id or "", []))
            fila_imagen = {
                "item_id": item_id,
                "ruta_storage": ruta,
                "tipo": "oficial" if item_id and not tiene_oficial else "variante",
                "etiquetas": ["cotizacion"],
                "origen": {"fuente": "pdf_cotizacion", "referencia": referencia, "huella": foto.huella},
                "subida_por": usuario_id,
            }
            try:
                imagen = (await db.table("imagenes").insert(fila_imagen).execute()).data[0]
            except Exception as error:
                # Otra subida simultánea ya puso la oficial de este artículo: se guarda como variante.
                if fila_imagen["tipo"] != "oficial":
                    raise
                registro.info("Oficial ya existente para %s (%s); se guarda como variante", codigo, error)
                fila_imagen["tipo"] = "variante"
                imagen = (await db.table("imagenes").insert(fila_imagen).execute()).data[0]
            por_clave[clave] = imagen
            if item_id:
                imagenes_por_item.setdefault(item_id, []).append(imagen)
            nuevas += 1
        imagen_por_orden[fila.orden] = str(imagen["id"])
    return nuevas, imagen_por_orden
