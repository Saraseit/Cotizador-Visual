"""Llamadas de texto y visión a OpenAI: leer una inspiración y traducir la propuesta.

Dos usos, los dos con respaldo para que nada quede bloqueado si OpenAI falla:
  - `analizar_inspiracion`: mira la imagen que subió el vendedor y propone los parámetros de la
    plantilla (composición, paleta, tipografía, tamaño de títulos…). Si falla, el llamador saca la
    paleta de la imagen con análisis local (`paleta_de_imagen`).
  - `traducir`: traduce en bloque los textos de una cotización. Si falla, el llamador usa el
    glosario de `idiomas.traducir_con_reglas`.

El nombre del modelo de texto no se escribe a mano: se pregunta a la cuenta qué modelos tiene y se
elige el primero de `PREFERENCIA_MODELOS` que exista (o el que se fije en OPENAI_MODELO_TEXTO).
Así no hay que adivinar el nombre del modelo del año en curso.
"""

from __future__ import annotations

import base64
import json
import logging
import re
from io import BytesIO
from typing import Any

from app.config import Configuracion

registro = logging.getLogger("cotizador.ia_texto")

# De mejor a peor para esta tarea: basta con que entienda español y lea una imagen.
PREFERENCIA_MODELOS = (
    "gpt-5.1-mini",
    "gpt-5.1",
    "gpt-5-mini",
    "gpt-5",
    "gpt-4.1-mini",
    "gpt-4.1",
    "gpt-4o-mini",
    "gpt-4o",
)
# Modelos que no sirven para chat aunque empiecen con "gpt".
_NO_TEXTO = ("image", "audio", "tts", "whisper", "realtime", "embedding", "moderation", "search", "transcribe")

LADO_MAXIMO_INSPIRACION = 1024
TEXTOS_POR_LLAMADA = 40


class ErrorIaTexto(Exception):
    """OpenAI no respondió o respondió algo que no se puede usar. El llamador usa su respaldo."""


_modelo_en_cache: dict[str, str] = {}


def _cliente(config: Configuracion) -> Any:
    if not (config.openai_api_key or "").strip():
        raise ErrorIaTexto("Falta OPENAI_API_KEY: no se puede usar la IA de texto.")
    from openai import AsyncOpenAI

    return AsyncOpenAI(api_key=config.openai_api_key)


async def elegir_modelo(config: Configuracion) -> str:
    """Modelo de texto a usar. Se pregunta una vez por proceso y se recuerda."""
    if (config.openai_modelo_texto or "").strip():
        return config.openai_modelo_texto.strip()
    if "modelo" in _modelo_en_cache:
        return _modelo_en_cache["modelo"]

    cliente = _cliente(config)
    try:
        pagina = await cliente.models.list()
        disponibles = sorted(m.id for m in pagina.data)
    except Exception as error:  # red, llave inválida, permisos
        raise ErrorIaTexto(f"No se pudo consultar los modelos de OpenAI: {error}") from error

    elegido = _mejor_modelo(disponibles)
    if not elegido:
        raise ErrorIaTexto("La cuenta de OpenAI no tiene ningún modelo de texto disponible.")
    _modelo_en_cache["modelo"] = elegido
    registro.info("Modelo de texto elegido: %s", elegido)
    return elegido


def _mejor_modelo(disponibles: list[str]) -> str:
    """El primero de la preferencia que exista, aceptando variantes con fecha (gpt-5-mini-2026-01-01)."""
    for preferido in PREFERENCIA_MODELOS:
        if preferido in disponibles:
            return preferido
        fechados = [m for m in disponibles if m.startswith(f"{preferido}-")]
        if fechados:
            return sorted(fechados)[-1]
    sirven = [m for m in disponibles if m.startswith("gpt-") and not any(p in m for p in _NO_TEXTO)]
    return sorted(sirven)[0] if sirven else ""


def _json_de_texto(contenido: str) -> dict[str, Any]:
    """Acepta JSON pelón o envuelto en ```json ... ```."""
    limpio = re.sub(r"^```(?:json)?|```$", "", contenido.strip(), flags=re.M).strip()
    try:
        datos = json.loads(limpio)
    except json.JSONDecodeError as error:
        raise ErrorIaTexto(f"La respuesta no es JSON: {contenido[:160]}") from error
    if not isinstance(datos, dict):
        raise ErrorIaTexto("La respuesta no es un objeto JSON.")
    return datos


async def _pedir_json(config: Configuracion, mensajes: list[dict[str, Any]]) -> dict[str, Any]:
    cliente = _cliente(config)
    modelo = await elegir_modelo(config)
    try:
        respuesta = await cliente.chat.completions.create(
            model=modelo, messages=mensajes, response_format={"type": "json_object"}
        )
    except Exception as error:
        # Algunos modelos no aceptan response_format: se reintenta pidiendo el JSON en el prompt.
        registro.warning("Reintento sin response_format en %s: %s", modelo, error)
        try:
            respuesta = await cliente.chat.completions.create(model=modelo, messages=mensajes)
        except Exception as fallo:
            raise ErrorIaTexto(f"OpenAI no respondió ({modelo}): {fallo}") from fallo
    contenido = (respuesta.choices[0].message.content or "").strip() if respuesta.choices else ""
    if not contenido:
        raise ErrorIaTexto("OpenAI respondió vacío.")
    return _json_de_texto(contenido)


# ---------------------------------------------------------------------------
# Inspiración -> parámetros de plantilla
# ---------------------------------------------------------------------------

_INSTRUCCION_INSPIRACION = """Eres director de arte de Minimal 4.0, una empresa de renta de mobiliario para eventos en Mérida.
Vas a mirar una imagen de inspiración y proponer con qué parámetros armar una presentación editorial en PDF.

Responde SÓLO un objeto JSON con estas llaves:
  "nombre": 2 a 4 palabras que nombren el estilo (por ejemplo "Editorial cálido").
  "descripcion": una frase corta en español sobre el estilo.
  "composicion": "editorial" (portada con foto arriba y título abajo, mucho aire),
                 "revista" (fotos a toda página con los títulos encima) o
                 "catalogo" (denso, muchas piezas por página, poco texto).
  "tipografia_titulos": "everett" (grotesca ancha) o "bebas" (condensada, títulos muy altos).
  "escala_titulos": número entre 0.6 y 1.3. 1.0 es un título que llena el ancho.
  "fotos_a_sangre": true si las fotos deben llegar al borde de la página, false si van con margen.
  "piezas_por_pagina": 1, 2, 4 o 6 piezas de mobiliario por página.
  "mostrar_manifiesto": true si va una página de frases de marca sobre foto oscura.
  "mostrar_cierre": true si va una página de ambiente antes del resumen de precios.
  "paleta": {"fondo": "#RRGGBB", "texto": "#RRGGBB", "acento": "#RRGGBB"} tomada de la imagen.
            El fondo es el color de papel, el texto debe contrastar con él y el acento es para los títulos.

No uses verde menta (#B5FFBF): ese color está reservado para el logotipo de la marca."""


async def analizar_inspiracion(imagen: bytes, config: Configuracion) -> dict[str, Any]:
    """Parámetros de plantilla propuestos por la IA a partir de la imagen. Lanza ErrorIaTexto si falla."""
    mensajes = [
        {"role": "system", "content": _INSTRUCCION_INSPIRACION},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Analiza esta inspiración y responde el JSON."},
                {"type": "image_url", "image_url": {"url": _data_uri(imagen)}},
            ],
        },
    ]
    return await _pedir_json(config, mensajes)


def _data_uri(imagen: bytes) -> str:
    from PIL import Image

    original = Image.open(BytesIO(imagen))
    original.thumbnail((LADO_MAXIMO_INSPIRACION, LADO_MAXIMO_INSPIRACION))
    buffer = BytesIO()
    original.convert("RGB").save(buffer, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


# ---------------------------------------------------------------------------
# Traducción
# ---------------------------------------------------------------------------

_INSTRUCCION_TRADUCCION = """Traduces textos de una propuesta de renta de mobiliario para eventos, de una empresa mexicana, a {idioma}.

Reglas:
  - Devuelve SÓLO un objeto JSON: la misma llave numérica que recibiste, con la traducción como valor.
  - Respeta nombres propios, marcas y nombres de modelo de mueble (Tiffany, Crossback, Thonet, Acapulco).
  - Conserva las mayúsculas del original: si el texto viene todo en mayúsculas, tradúcelo en mayúsculas.
  - NO conviertas medidas ni números: deja "1.80", "270 X 120 CM" y los precios tal como están.
  - Es lenguaje de eventos: "periquera" es cocktail table, "montaje" es setup, "flete" es freight."""

_IDIOMAS = {"en": "inglés de Estados Unidos"}


async def traducir(textos: list[str], idioma: str, config: Configuracion) -> dict[str, str]:
    """Traduce en bloque. Devuelve {texto original: traducción}; los que fallen no aparecen."""
    limpios = [t for t in dict.fromkeys(textos) if t and t.strip()]
    if not limpios:
        return {}
    nombre_idioma = _IDIOMAS.get(idioma)
    if not nombre_idioma:
        raise ErrorIaTexto(f"Idioma no soportado: {idioma}")

    traducciones: dict[str, str] = {}
    for inicio in range(0, len(limpios), TEXTOS_POR_LLAMADA):
        tanda = limpios[inicio : inicio + TEXTOS_POR_LLAMADA]
        entrada = {str(i): texto for i, texto in enumerate(tanda)}
        datos = await _pedir_json(
            config,
            [
                {"role": "system", "content": _INSTRUCCION_TRADUCCION.format(idioma=nombre_idioma)},
                {"role": "user", "content": json.dumps(entrada, ensure_ascii=False)},
            ],
        )
        for indice, texto in entrada.items():
            traducido = datos.get(indice)
            if isinstance(traducido, str) and traducido.strip():
                traducciones[texto] = traducido.strip()
    if not traducciones:
        raise ErrorIaTexto("OpenAI no devolvió ninguna traducción utilizable.")
    return traducciones
