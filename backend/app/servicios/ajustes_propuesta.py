"""Ajustes del PDF de la propuesta base: título, logotipo, imagen al pie, notas y campos extra.

Se editan en la pantalla "Formato del PDF" y se guardan en la tabla `ajustes` (clave 'propuesta_base').
Son pocos y sencillos a propósito: cambian lo que se imprime, no cómo se calcula la propuesta.
"""

from __future__ import annotations

import base64
import logging
import re
from datetime import date
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from pydantic import ValidationError

from app.db.modelos import AjustesPropuesta, CampoPropuesta

registro = logging.getLogger("cotizador.ajustes")

CLAVE = "propuesta_base"
LOGOTIPO_MARCA = Path(__file__).resolve().parent.parent / "marca" / "logotipo.png"
LADO_LOGOTIPO = 1200  # px: nítido a 200 pt de ancho
LADO_PIE = 1800

_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_HORA = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


async def leer(db: Any) -> AjustesPropuesta:
    """Ajustes guardados; si no hay (o ya no son válidos), los de por defecto (con las notas de siempre)."""
    respuesta = await db.table("ajustes").select("valor").eq("clave", CLAVE).limit(1).execute()
    if not respuesta.data:
        return AjustesPropuesta()
    try:
        return AjustesPropuesta.model_validate(respuesta.data[0]["valor"] or {})
    except ValidationError as error:
        registro.warning("Ajustes de la propuesta inválidos, se usan los de por defecto: %s", error)
        return AjustesPropuesta()


async def guardar(db: Any, ajustes: AjustesPropuesta, usuario_id: str) -> None:
    await db.table("ajustes").upsert(
        {"clave": CLAVE, "valor": ajustes.model_dump(mode="json"), "actualizado_por": usuario_id},
        on_conflict="clave",
    ).execute()


def validar_valor(campo: CampoPropuesta, valor: str) -> str:
    """El valor limpio; ValueError si no tiene el formato del campo."""
    valor = (valor or "").strip()
    if not valor:
        return ""
    if campo.tipo == "fecha":
        if not _FECHA.match(valor):
            raise ValueError(f"{campo.etiqueta}: la fecha debe ir como AAAA-MM-DD.")
        date.fromisoformat(valor)  # fechas imposibles (31 de febrero) también fallan
    elif campo.tipo == "hora" and not _HORA.match(valor):
        raise ValueError(f"{campo.etiqueta}: la hora debe ir como HH:MM.")
    return valor[:200]


def formatear(campo: CampoPropuesta, valor: str, idioma: str = "es") -> str:
    """Cómo se imprime: fechas dd/mm/aaaa (mm/dd/aaaa en inglés), horas 18:00 (6:00 PM en inglés)."""
    if campo.tipo == "fecha":
        try:
            dia = date.fromisoformat(valor)
        except ValueError:
            return valor
        return dia.strftime("%m/%d/%Y") if idioma == "en" else dia.strftime("%d/%m/%Y")
    if campo.tipo == "hora" and idioma == "en" and _HORA.match(valor):
        horas, minutos = (int(v) for v in valor.split(":"))
        return f"{(horas % 12) or 12}:{minutos:02d} {'AM' if horas < 12 else 'PM'}"
    return valor


def campos_impresos(ajustes: AjustesPropuesta, valores: dict[str, str], idioma: str = "es") -> list[tuple[str, str]]:
    """(etiqueta, valor) de los campos con algo que imprimir: el de la cotización o el predeterminado."""
    impresos: list[tuple[str, str]] = []
    for campo in ajustes.campos:
        valor = (valores.get(campo.id) or "").strip() or campo.predeterminado.strip()
        if valor:
            impresos.append((campo.etiqueta, formatear(campo, valor, idioma)))
    return impresos


def a_data_uri(datos: bytes, lado_maximo: int) -> str:
    """PNG (conserva transparencia) reducido, para incrustarlo en el PDF."""
    from PIL import Image

    imagen = Image.open(BytesIO(datos))
    imagen.thumbnail((lado_maximo, lado_maximo))
    buffer = BytesIO()
    imagen.convert("RGBA").save(buffer, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


@lru_cache(maxsize=1)
def logotipo_de_marca() -> str:
    return a_data_uri(LOGOTIPO_MARCA.read_bytes(), LADO_LOGOTIPO)


async def imagenes(storage: Any, ajustes: AjustesPropuesta) -> dict[str, str]:
    """hueco ('logotipo', 'pie') -> data URI. Si el logotipo subido ya no está, va el de la marca."""
    resultado = {"logotipo": logotipo_de_marca()}
    for hueco, ruta, lado in (("logotipo", ajustes.logotipo_ruta, LADO_LOGOTIPO), ("pie", ajustes.pie_ruta, LADO_PIE)):
        if not ruta:
            continue
        try:
            resultado[hueco] = a_data_uri(await storage.descargar(storage.bucket_imagenes, ruta), lado)
        except (HTTPException, OSError, ValueError) as error:
            registro.warning("No se pudo cargar la imagen '%s' del PDF (%s): %s", hueco, ruta, error)
    return resultado
