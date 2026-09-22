"""Clasificación de partidas que no son mobiliario sino cargos: flete y montaje.

Estas partidas no se imprimen como renglón con foto: se suman y se muestran abajo, junto al
subtotal (Subtotal · Flete · Montaje · IVA · Total). Se reconocen por palabras de la descripción o
porque vienen en la sección MONTAJE del PDF del sistema. En Revisar el vendedor puede corregir la
clasificación a mano.
"""

from __future__ import annotations

import re
from typing import Literal

Cargo = Literal["flete", "montaje"]

_PALABRAS: list[tuple[Cargo, re.Pattern[str]]] = [
    ("flete", re.compile(r"\b(FLETES?|TRANSPORTES?|TRASLADOS?)\b", re.IGNORECASE)),
    ("montaje", re.compile(r"\b(MONTAJES?|DESMONTAJES?|INSTALACI[OÓ]N(ES)?)\b", re.IGNORECASE)),
]
# "TEEPEE ... ( SIN INSTALACION ELECTRICA )", "(NO INCLUYE MONTAJE)": la palabra aparece negada.
_NEGACION = re.compile(r"\b(SIN|NO\s+INCLUYEN?|EXCEPTO|NO\s+APLICA)\W*$", re.IGNORECASE)
_SECCION_MONTAJE = re.compile(r"^\s*MONTAJES?\s*$", re.IGNORECASE)


def clasificar_cargo(descripcion: str, categoria: str = "") -> Cargo | None:
    """'flete' o 'montaje' si la partida es un cargo; None si es una partida normal.

    Si la descripción menciona ambas cosas ("FLETE Y MONTAJE") gana la que aparece primero.
    """
    texto = descripcion or ""
    encontrados: list[tuple[int, Cargo]] = []
    for cargo, patron in _PALABRAS:
        for coincidencia in patron.finditer(texto):
            if _NEGACION.search(texto[: coincidencia.start()]):
                continue
            encontrados.append((coincidencia.start(), cargo))
            break
    if encontrados:
        return min(encontrados)[1]
    if _SECCION_MONTAJE.match(categoria or ""):
        return "montaje"
    return None
