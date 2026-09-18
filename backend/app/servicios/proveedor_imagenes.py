"""Generación de variantes de imagen a partir de la foto oficial de un ítem.

`ProveedorImagenes` es la interfaz; `ProveedorOpenAI` la implementación real (gpt-image-1,
endpoint de edición con imagen base). `ProveedorSimulado` sirve para desarrollar sin gastar
créditos: devuelve la imagen base con un tinte y una etiqueta.

El prompt final = prompt de estilo fijo (config.PROMPT_ESTILO_FIJO) + petición del vendedor.
"""

from __future__ import annotations

import base64
from io import BytesIO
from typing import Protocol

from app.config import Configuracion


class ErrorProveedorImagenes(Exception):
    """El proveedor externo falló. El router lo traduce a 502 sin afectar la cotización."""


class ProveedorImagenes(Protocol):
    nombre: str
    modelo: str

    async def generar_variantes(self, imagen_base: bytes, peticion: str, cantidad: int) -> list[bytes]: ...


def construir_prompt(prompt_estilo: str, peticion: str) -> str:
    return f"{prompt_estilo.strip()}\n\nCambio solicitado por el cliente: {peticion.strip()}"


LADO_MAXIMO_BASE = 1024


def preparar_imagen_base(datos: bytes) -> bytes:
    """Normaliza la imagen base para el proveedor: PNG RGBA con lado mayor ≤ 1024 px.

    Así da igual que en la biblioteca esté como JPG o WebP, y no se mandan fotos enormes.
    """
    from PIL import Image, UnidentifiedImageError

    try:
        imagen = Image.open(BytesIO(datos))
        imagen.load()
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise ErrorProveedorImagenes(f"La imagen base no es válida: {error}") from error

    imagen = imagen.convert("RGBA")
    imagen.thumbnail((LADO_MAXIMO_BASE, LADO_MAXIMO_BASE))
    buffer = BytesIO()
    imagen.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


class ProveedorOpenAI:
    nombre = "openai"

    def __init__(self, api_key: str, modelo: str, prompt_estilo: str, calidad: str = "medium"):
        from openai import AsyncOpenAI

        self._cliente = AsyncOpenAI(api_key=api_key)
        self.modelo = modelo
        self._prompt_estilo = prompt_estilo
        self._calidad = calidad

    async def generar_variantes(self, imagen_base: bytes, peticion: str, cantidad: int) -> list[bytes]:
        from openai import OpenAIError

        base_png = preparar_imagen_base(imagen_base)
        try:
            respuesta = await self._cliente.images.edit(
                model=self.modelo,
                image=("base.png", base_png, "image/png"),
                prompt=construir_prompt(self._prompt_estilo, peticion),
                n=cantidad,
                size="1024x1024",
                quality=self._calidad,  # type: ignore[arg-type]
                input_fidelity="high",  # conserva la forma y detalles de la pieza original
            )
        except OpenAIError as error:
            raise ErrorProveedorImagenes(f"OpenAI no pudo generar las imágenes: {error}") from error
        except Exception as error:  # red, timeouts, etc.
            raise ErrorProveedorImagenes(f"Error inesperado al llamar a OpenAI: {error}") from error

        salidas: list[bytes] = []
        for dato in respuesta.data or []:
            if dato.b64_json:
                salidas.append(base64.b64decode(dato.b64_json))
        if not salidas:
            raise ErrorProveedorImagenes("OpenAI respondió sin imágenes.")
        return salidas


class ProveedorSimulado:
    """Variantes falsas para desarrollo local. No llama a ningún servicio externo."""

    nombre = "simulado"
    modelo = "simulado-v1"

    _TINTES = [(140, 74, 47), (35, 87, 65), (107, 78, 10), (87, 83, 74)]

    def __init__(self, prompt_estilo: str = ""):
        self._prompt_estilo = prompt_estilo

    async def generar_variantes(self, imagen_base: bytes, peticion: str, cantidad: int) -> list[bytes]:
        from PIL import Image, ImageDraw, ImageFont

        base = Image.open(BytesIO(preparar_imagen_base(imagen_base))).convert("RGBA")

        salidas: list[bytes] = []
        for indice in range(cantidad):
            tinte = self._TINTES[indice % len(self._TINTES)]
            capa = Image.new("RGBA", base.size, (*tinte, 90))
            variante = Image.alpha_composite(base, capa).convert("RGB")
            dibujo = ImageDraw.Draw(variante)
            fuente = ImageFont.load_default(size=max(14, base.size[0] // 24))
            dibujo.text((12, 12), f"SIMULADO {indice + 1}: {peticion[:40]}", fill=(255, 255, 255), font=fuente)
            buffer = BytesIO()
            variante.save(buffer, format="PNG")
            salidas.append(buffer.getvalue())
        return salidas


def obtener_proveedor(config: Configuracion) -> ProveedorImagenes:
    proveedor = config.proveedor_efectivo  # 'openai' sin llave cae a 'simulado'
    if proveedor == "simulado":
        return ProveedorSimulado(config.prompt_estilo_fijo)
    if proveedor == "openai":
        if not config.openai_api_key:
            raise ErrorProveedorImagenes("Falta OPENAI_API_KEY para generar imágenes.")
        return ProveedorOpenAI(
            api_key=config.openai_api_key,
            modelo=config.openai_modelo_imagenes,
            prompt_estilo=config.prompt_estilo_fijo,
            calidad=config.openai_calidad_imagenes,
        )
    raise ErrorProveedorImagenes(f"Proveedor de imágenes desconocido: '{proveedor}'.")
