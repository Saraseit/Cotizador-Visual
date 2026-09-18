"""Resolución de ítems del export contra el catálogo y elección de imagen sugerida.

Reglas (versión piloto):
  - Match exacto por código normalizado (mayúsculas, sin espacios). Sin matching difuso.
  - Con match: imagen 'oficial' del ítem si existe; si no, la 'variante' con más usos;
    si no hay ninguna, sin imagen. Las imágenes 'generada' nunca se sugieren solas.
  - Sin match (o sin código): el ítem se conserva como 'ad_hoc' con item_id nulo.

Todas las funciones son puras para poder probarlas sin base de datos.
"""

import re
from dataclasses import dataclass
from typing import Any, Iterable

from app.db.modelos import TipoItem

_ESPACIOS = re.compile(r"\s+")


def normalizar_codigo(codigo: str | None) -> str:
    """'  sil-001 ' -> 'SIL-001'. Cadena vacía si no hay código."""
    if codigo is None:
        return ""
    return _ESPACIOS.sub("", str(codigo)).upper()


@dataclass(frozen=True)
class ResultadoMatch:
    item_id: str | None
    imagen_id: str | None
    tipo_item: TipoItem

    @property
    def es_catalogo(self) -> bool:
        return self.tipo_item == "catalogo"


def elegir_imagen_sugerida(imagenes: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    """Devuelve la imagen que se asigna automáticamente a un ítem con match."""
    lista = list(imagenes)
    for imagen in lista:
        if imagen.get("tipo") == "oficial":
            return imagen
    variantes = [i for i in lista if i.get("tipo") == "variante"]
    if not variantes:
        return None
    # Más usos primero; desempate estable por id para que el resultado sea determinista.
    return max(variantes, key=lambda i: (int(i.get("usos") or 0), -_orden_id(i)))


def _orden_id(imagen: dict[str, Any]) -> int:
    # Sólo para desempatar de forma estable; el id es uuid -> usamos su hash textual.
    return sum(ord(c) for c in str(imagen.get("id", "")))


def resolver_item(
    codigo: str | None,
    catalogo_por_codigo: dict[str, dict[str, Any]],
    imagenes_por_item: dict[str, list[dict[str, Any]]],
) -> ResultadoMatch:
    """Resuelve una fila. `catalogo_por_codigo` debe estar indexado por código normalizado."""
    clave = normalizar_codigo(codigo)
    item = catalogo_por_codigo.get(clave) if clave else None
    if item is None:
        return ResultadoMatch(item_id=None, imagen_id=None, tipo_item="ad_hoc")

    imagen = elegir_imagen_sugerida(imagenes_por_item.get(str(item["id"]), []))
    return ResultadoMatch(
        item_id=str(item["id"]),
        imagen_id=str(imagen["id"]) if imagen else None,
        tipo_item="catalogo",
    )


def resolver_filas(
    codigos: Iterable[str | None],
    catalogo_por_codigo: dict[str, dict[str, Any]],
    imagenes_por_item: dict[str, list[dict[str, Any]]],
) -> list[ResultadoMatch]:
    return [resolver_item(c, catalogo_por_codigo, imagenes_por_item) for c in codigos]


def indexar_catalogo(items: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {normalizar_codigo(i["codigo"]): i for i in items}


def agrupar_imagenes(imagenes: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grupos: dict[str, list[dict[str, Any]]] = {}
    for imagen in imagenes:
        if imagen.get("item_id"):
            grupos.setdefault(str(imagen["item_id"]), []).append(imagen)
    return grupos
