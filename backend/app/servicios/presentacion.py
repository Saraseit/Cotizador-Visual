"""Presentación editorial: cotización + plantilla + lo que configuró el vendedor -> HTML -> PDF.

Reglas de marca que no dependen de la configuración:
  - Logotipo y monograma son los archivos de `app/marca` (recoloreados sólo a colores de marca).
  - Tipografías de marca: Everett (si sus archivos están en `app/fuentes/marca`; si no, Public Sans,
    la misma que usa la presentación de ejemplo) y Bebas Neue.
  - Los identificadores de marca van en menta (#B5FFBF), negro o crema.
  - Al final siempre va el concentrado por sección con subtotal, flete, montaje, IVA y total (sin
    importes si el vendedor oculta los precios).

Lo que sí cambia por propuesta: la plantilla (composición, paleta, tipografía, tamaño de títulos,
piezas por página), la moneda (pesos o dólares al tipo de cambio que ponga el vendedor) y el idioma.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import ValidationError

from app.db.modelos import (
    PREFIJO_MONTAJE,
    descripcion_impresa,
    ConfigPresentacion,
    CotizacionDetalle,
    CotizacionItem,
    Paleta,
    PaletaGuardada,
    ParametrosPlantilla,
    SeccionPresentacion,
    SeccionVista,
)
from app.servicios import idiomas
from app.servicios.render_pdf import formatear_cantidad, html_a_pdf

registro = logging.getLogger("cotizador.presentacion")

APP = Path(__file__).resolve().parent.parent
DIR_PLANTILLAS = APP / "plantillas"
DIR_MARCA = APP / "marca"
DIR_FUENTES = APP / "fuentes"
DIR_FUENTES_MARCA = DIR_FUENTES / "marca"
PLANTILLA = "presentacion_editorial.html"

# Colores de los identificadores de marca (fijos).
MENTA = "#B5FFBF"
CREMA = "#FFFCF7"
NEGRO = "#000000"

# Página de la presentación de ejemplo: 810 x 1080 pt (proporción 3:4).
ANCHO_PAGINA = 810
ALTO_PAGINA = 1080
MARGEN = 40

LADO_FOTO_GRANDE = 1800  # portada, manifiesto, cierre y montajes
LADO_FOTO_PIEZA = 1000  # fotos de las partidas
REFERENCIAS_MAXIMAS = 6  # fotos de partidas que se mandan como referencia para el montaje
INSPIRACIONES_MAXIMAS = 3  # imágenes de la plantilla que además guían el estilo del montaje
PARTIDAS_EN_PROMPT = 12

TITULO_SIN_SECCION = "MOBILIARIO"

# Paletas que trae la app. El equipo puede guardar las suyas (tabla `paletas`).
PALETAS_PREDEFINIDAS: list[tuple[str, Paleta]] = [
    ("Crema", Paleta(fondo="#FFFCF7", texto="#111111", acento="#603D22")),
    ("Arena", Paleta(fondo="#F2EADF", texto="#2A2118", acento="#8A5A3B")),
    ("Lino", Paleta(fondo="#F6F2EA", texto="#1F1B16", acento="#9A7B4F")),
    ("Olivo", Paleta(fondo="#EAEDE1", texto="#1F2418", acento="#55613A")),
    ("Salvia", Paleta(fondo="#E7EDE8", texto="#1C2620", acento="#4E7360")),
    ("Terracota", Paleta(fondo="#FBF0E8", texto="#2B1A12", acento="#B4552D")),
    ("Niebla", Paleta(fondo="#EFF1F3", texto="#1A1F24", acento="#4A6076")),
    ("Marino", Paleta(fondo="#EDF1F6", texto="#111B27", acento="#1F3D63")),
    ("Vino", Paleta(fondo="#F7EEEE", texto="#231316", acento="#7A2233")),
    ("Noche", Paleta(fondo="#101010", texto="#F5F5F5", acento="#C9A27E")),
    ("Carbón", Paleta(fondo="#1C1E1F", texto="#F2F0EC", acento="#9BB29E")),
    ("Tinta", Paleta(fondo="#14181F", texto="#EEF1F5", acento="#C2A46A")),
]


def paletas_predefinidas() -> list[PaletaGuardada]:
    return [PaletaGuardada(nombre=nombre, paleta=paleta, predefinida=True) for nombre, paleta in PALETAS_PREDEFINIDAS]


# ---------------------------------------------------------------------------
# Secciones y configuración
# ---------------------------------------------------------------------------

@dataclass
class Grupo:
    clave: str
    items: list[CotizacionItem] = field(default_factory=list)


def agrupar_por_seccion(detalle: CotizacionDetalle) -> list[Grupo]:
    """Partidas de mobiliario agrupadas por su sección del PDF, en el orden en que aparece cada una.

    Flete y montaje no forman sección: van en el concentrado.
    """
    grupos: dict[str, Grupo] = {}
    for item in sorted(detalle.items, key=lambda i: i.orden):
        if item.cargo:
            continue
        grupos.setdefault(item.categoria, Grupo(item.categoria)).items.append(item)
    return list(grupos.values())


def titulo_por_defecto(clave: str) -> str:
    return (clave or TITULO_SIN_SECCION).strip().upper()[:40]


def config_por_defecto(detalle: CotizacionDetalle) -> ConfigPresentacion:
    return ConfigPresentacion(
        evento=(detalle.nombre_cliente or "")[:80],
        secciones=[SeccionPresentacion(clave=g.clave, titulo=titulo_por_defecto(g.clave)) for g in agrupar_por_seccion(detalle)],
    )


def migrar_config(crudo: dict[str, Any]) -> dict[str, Any]:
    """Configuraciones guardadas antes de las plantillas traían paleta y tipografía sueltas."""
    datos = dict(crudo)
    parametros = dict(datos.get("parametros") or {})
    for viejo in ("paleta", "tipografia_titulos"):
        if viejo in datos and viejo not in parametros:
            parametros[viejo] = datos.pop(viejo)
    if parametros:
        datos["parametros"] = parametros
    return datos


def leer_config(crudo: dict[str, Any] | None, detalle: CotizacionDetalle) -> ConfigPresentacion:
    """Config guardada; si no hay (o ya no es válida) se arma la de por defecto."""
    if not crudo:
        return config_por_defecto(detalle)
    try:
        return ConfigPresentacion.model_validate(migrar_config(crudo))
    except ValidationError as error:
        registro.warning("Config de presentación inválida, se usa la de por defecto: %s", error)
        return config_por_defecto(detalle)


def secciones_vista(config: ConfigPresentacion, detalle: CotizacionDetalle) -> list[SeccionVista]:
    """Secciones actuales de la cotización con lo que el vendedor configuró para cada una.

    Si la cotización cambió (secciones nuevas o que ya no existen), manda la cotización.
    """
    ajustes = {s.clave: s for s in config.secciones}
    vistas: list[SeccionVista] = []
    for grupo in agrupar_por_seccion(detalle):
        ajuste = ajustes.get(grupo.clave) or SeccionPresentacion(clave=grupo.clave, titulo=titulo_por_defecto(grupo.clave))
        vistas.append(
            SeccionVista(
                clave=grupo.clave,
                titulo=ajuste.titulo.strip() or titulo_por_defecto(grupo.clave),
                texto=ajuste.texto,
                incluir=ajuste.incluir,
                categoria=grupo.clave,
                partidas=len(grupo.items),
                piezas=sum(i.cantidad for i in grupo.items),
                importe=round(sum(i.importe for i in grupo.items), 2),
                con_imagen=sum(1 for i in grupo.items if i.imagen_id),
            )
        )
    return vistas


def hueco_montaje(clave: str) -> str:
    return f"{PREFIJO_MONTAJE}{clave}"


# ---------------------------------------------------------------------------
# Moneda e idioma
# ---------------------------------------------------------------------------

def dinero_de(config: ConfigPresentacion) -> idiomas.Dinero:
    return idiomas.Dinero(moneda=config.moneda, tipo_cambio=config.tipo_cambio)


def traductor_de(config: ConfigPresentacion) -> idiomas.Traductor:
    return idiomas.Traductor(idioma=config.idioma, cache=dict(config.traducciones))


def textos_traducibles(detalle: CotizacionDetalle, config: ConfigPresentacion, vistas: list[SeccionVista]) -> list[str]:
    """Todo lo que hay que mandar a traducir de esta cotización.

    Quedan fuera las descripciones que el vendedor ya ajustó: son correcciones deliberadas.
    """
    textos: list[str] = [config.titulo, config.evento]
    textos += [v.titulo for v in vistas] + [v.texto for v in vistas if v.texto.strip()]
    textos += [t for t in config.manifiesto + config.cierre if t.strip()]
    for item in detalle.items:
        if item.cargo or (item.descripcion_editada or "").strip():
            continue
        textos.append(item.descripcion_origen)
        if item.item and item.item.medidas:
            textos.append(item.item.medidas)
    return [t.strip() for t in textos if t and t.strip()]


# ---------------------------------------------------------------------------
# Medidas de texto (para que los títulos gigantes llenen el ancho sin desbordarse)
# ---------------------------------------------------------------------------

def archivos_everett() -> dict[int, Path]:
    """Archivos de Everett presentes en app/fuentes/marca, por peso (300, 400, 500)."""
    pesos = {"light": 300, "regular": 400, "book": 400, "medium": 500}
    encontrados: dict[int, Path] = {}
    if DIR_FUENTES_MARCA.is_dir():
        for ruta in sorted(DIR_FUENTES_MARCA.iterdir()):
            nombre = ruta.stem.lower()
            if "everett" not in nombre or ruta.suffix.lower() not in {".otf", ".ttf", ".woff", ".woff2"} or "italic" in nombre:
                continue
            for clave, peso in pesos.items():
                if clave in nombre:
                    encontrados.setdefault(peso, ruta)
    return encontrados


def _archivo_para_medir(tipografia: str) -> Path:
    if tipografia == "bebas":
        return DIR_FUENTES / "BebasNeue-Regular.ttf"
    everett = archivos_everett()
    if 400 in everett and everett[400].suffix.lower() in {".otf", ".ttf"}:
        return everett[400]
    return DIR_FUENTES / "PublicSans-Regular.ttf"


@lru_cache(maxsize=8)
def _metricas(ruta: str) -> tuple[dict[str, float], float]:
    """Ancho de avance de cada carácter en em, y el promedio para los que falten."""
    from fontTools.ttLib import TTFont

    fuente = TTFont(ruta, lazy=True)
    unidades = fuente["head"].unitsPerEm
    mapa = fuente.getBestCmap()
    avances = fuente["hmtx"].metrics
    anchos = {chr(codigo): avances[glifo][0] / unidades for codigo, glifo in mapa.items() if glifo in avances}
    promedio = sum(anchos.get(c, 0.6) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ") / 26
    return anchos, promedio


def ancho_em(texto: str, tipografia: str, espaciado_em: float = -0.02) -> float:
    anchos, promedio = _metricas(str(_archivo_para_medir(tipografia)))
    return sum(anchos.get(c, promedio) for c in texto) + espaciado_em * max(len(texto) - 1, 0)


def tamano_titulo(texto: str, ancho_pt: float, maximo_pt: float, tipografia: str, lineas: int = 1) -> float:
    """Tamaño (pt) para que el título en mayúsculas llene `ancho_pt` en a lo más `lineas` renglones.

    Con varios renglones, la palabra más larga tiene que caber sola en uno.
    """
    texto = " ".join(texto.upper().split()) or "-"
    palabra_mayor = max(ancho_em(p, tipografia) for p in texto.split(" "))
    total = ancho_em(texto, tipografia)
    por_palabra = ancho_pt / palabra_mayor
    por_total = ancho_pt * lineas * (0.92 if lineas > 1 else 1) / total
    return round(max(18.0, min(maximo_pt, por_palabra, por_total)), 1)


# ---------------------------------------------------------------------------
# Imágenes
# ---------------------------------------------------------------------------

def _hex_a_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def _rgb_a_hex(rgb: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{max(0, min(255, int(c))):02X}" for c in rgb)


def mezclar(color: str, otro: str, proporcion: float) -> str:
    """Mezcla `proporcion` de `otro` sobre `color` (para líneas y textos suaves de cualquier paleta)."""
    a, b = _hex_a_rgb(color), _hex_a_rgb(otro)
    return "#" + "".join(f"{round(x + (y - x) * proporcion):02X}" for x, y in zip(a, b))


def luminancia(color: str) -> float:
    r, g, b = (c / 255 for c in _hex_a_rgb(color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def es_oscuro(color: str) -> bool:
    return luminancia(color) < 0.45


def paleta_de_imagen(datos: bytes) -> Paleta:
    """Paleta sacada de la imagen con análisis local; es el respaldo cuando la IA no está disponible.

    Fondo: el color dominante aclarado u oscurecido hasta que sirva de papel.
    Acento: el color más saturado de la imagen. Texto: casi negro o casi blanco según el fondo.
    """
    from PIL import Image

    imagen = Image.open(BytesIO(datos)).convert("RGB")
    imagen.thumbnail((200, 200))
    reducida = imagen.quantize(colors=8, method=Image.Quantize.MEDIANCUT).convert("RGB")
    colores = sorted(reducida.getcolors(maxcolors=64) or [], key=lambda c: c[0], reverse=True)
    if not colores:
        return Paleta()

    dominante = colores[0][1]
    saturacion = lambda c: (max(c) - min(c)) / 255  # noqa: E731
    candidatos = [c for _, c in colores if saturacion(c) > 0.12]
    acento = max(candidatos, key=saturacion) if candidatos else dominante

    if luminancia(_rgb_a_hex(dominante)) >= 0.45:  # papel claro
        fondo = tuple(int(c + (255 - c) * 0.72) for c in dominante)
        texto = (17, 17, 17)
        acento = tuple(int(c * 0.62) for c in acento)
    else:  # papel oscuro
        fondo = tuple(int(c * 0.45) for c in dominante)
        texto = (244, 242, 238)
        acento = tuple(int(c + (255 - c) * 0.35) for c in acento)
    return Paleta(fondo=_rgb_a_hex(fondo), texto=_rgb_a_hex(texto), acento=_rgb_a_hex(acento))


@lru_cache(maxsize=16)
def logo(nombre: str, color: str) -> str:
    """Logo de marca (monograma, logotipo, logotipo_leyendas) en un color de marca, como data URI."""
    from PIL import Image

    if color not in {MENTA, CREMA, NEGRO}:
        raise ValueError(f"{color} no es un color de marca")
    original = Image.open(DIR_MARCA / f"{nombre}.png").convert("RGBA")
    teñido = Image.new("RGBA", original.size, (*_hex_a_rgb(color), 255))
    teñido.putalpha(original.getchannel("A"))
    buffer = BytesIO()
    teñido.save(buffer, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def foto_a_data_uri(datos: bytes, lado_maximo: int) -> str:
    from PIL import Image

    imagen = Image.open(BytesIO(datos))
    imagen.thumbnail((lado_maximo, lado_maximo))
    buffer = BytesIO()
    if imagen.mode in ("RGBA", "LA", "P") and imagen.convert("RGBA").getextrema()[3][0] < 255:
        imagen.convert("RGBA").save(buffer, format="PNG", optimize=True)  # recorte con transparencia
        mime = "image/png"
    else:
        imagen.convert("RGB").save(buffer, format="JPEG", quality=84, optimize=True)
        mime = "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(buffer.getvalue()).decode('ascii')}"


def a_jpeg(datos: bytes, lado_maximo: int = 2048) -> bytes:
    from PIL import Image

    imagen = Image.open(BytesIO(datos)).convert("RGB")
    imagen.thumbnail((lado_maximo, lado_maximo))
    buffer = BytesIO()
    imagen.save(buffer, format="JPEG", quality=88, optimize=True)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Prompt de montaje
# ---------------------------------------------------------------------------

def prompt_montaje(
    config: ConfigPresentacion,
    seccion: SeccionVista,
    items: list[CotizacionItem],
    indicaciones: str = "",
    inspiraciones: int = 0,
) -> str:
    lineas = [f"- {formatear_cantidad(i.cantidad)} x {descripcion_impresa(i).strip()}" for i in items[:PARTIDAS_EN_PROMPT]]
    if len(items) > PARTIDAS_EN_PROMPT:
        lineas.append(f"- y {len(items) - PARTIDAS_EN_PROMPT} piezas más de la misma sección")
    partes = [
        "Fotografía editorial realista de interiorismo para eventos, como para una revista de diseño: "
        f'el montaje de la sección "{seccion.titulo}"'
        + (f' para el evento "{config.evento}"' if config.evento.strip() else "")
        + ", de Minimal 4.0, renta de mobiliario para eventos en Mérida, Yucatán.",
        "Mobiliario que debe aparecer; las primeras imágenes adjuntas son fotos de esas mismas piezas, "
        "respeta su forma, material, color y proporciones:\n" + "\n".join(lineas),
    ]
    if inspiraciones:
        partes.append(
            f"Las últimas {inspiraciones} imágenes adjuntas son la inspiración de la propuesta: copia de ellas la "
            "atmósfera, la luz y el tratamiento de color, no el mobiliario."
        )
    if config.brief.strip():
        partes.append(f"Indicaciones del vendedor sobre el evento y el estilo: {config.brief.strip()}")
    if indicaciones.strip():
        partes.append(f"Para esta imagen en particular: {indicaciones.strip()}")
    paleta = config.parametros.paleta
    partes.append(
        f"Paleta de la presentación: fondo {paleta.fondo}, texto {paleta.texto}, acento {paleta.acento}. "
        "Luz cálida y natural, composición amplia y ordenada, encuadre horizontal, profundidad de campo suave. "
        "Sin personas en primer plano, sin texto, sin logotipos y sin marcas de agua."
    )
    return "\n\n".join(partes)


# ---------------------------------------------------------------------------
# Contexto de la plantilla
# ---------------------------------------------------------------------------

@dataclass
class PiezaRender:
    nombre: str
    detalle: str  # texto entre paréntesis de la descripción del sistema
    medidas: str
    cantidad: str
    precio_unitario: str
    importe: str
    foto: str | None


_PARENTESIS = re.compile(r"^(?P<nombre>[^(]+?)\s*\((?P<detalle>.+)\)\s*$")


def _pieza(item: CotizacionItem, fotos: dict[str, str], dinero: idiomas.Dinero, traducir: idiomas.Traductor) -> PiezaRender:
    editada = bool((item.descripcion_editada or "").strip())
    texto = descripcion_impresa(item)
    descripcion = " ".join((texto if editada else traducir(texto)).split())
    coincidencia = _PARENTESIS.match(descripcion)
    nombre, detalle = (coincidencia["nombre"], coincidencia["detalle"]) if coincidencia else (descripcion, "")
    medidas = traducir.medidas((item.item.medidas if item.item else "") or "")
    return PiezaRender(
        nombre=nombre,
        detalle=detalle,
        medidas=medidas,
        cantidad=formatear_cantidad(item.cantidad),
        precio_unitario=dinero(item.precio_unitario),
        importe=dinero(item.importe),
        foto=fotos.get(str(item.imagen_id)) if item.imagen_id else None,
    )


def _columnas(texto: str, respaldo: list[str]) -> list[str]:
    """Hasta 3 columnas: los párrafos del vendedor (separados por renglón en blanco) o el respaldo."""
    parrafos = [p.strip() for p in re.split(r"\n\s*\n", texto or "") if p.strip()]
    return (parrafos or respaldo)[:3]


def _paginas_de_piezas(piezas: list[PiezaRender], por_pagina: int) -> list[dict[str, Any]]:
    """Reparte las piezas según la plantilla: 1 grande, 2 en zigzag o rejilla de 4 o 6."""
    formato = {1: "solo", 2: "par"}.get(por_pagina, "rejilla")
    columnas = 3 if por_pagina == 6 else 2
    return [
        {"formato": formato, "columnas": columnas, "piezas": piezas[i : i + por_pagina]}
        for i in range(0, len(piezas), por_pagina)
    ]


def construir_contexto(
    detalle: CotizacionDetalle,
    config: ConfigPresentacion,
    vistas: list[SeccionVista],
    fotos_huecos: dict[str, str],
    conceptuales: set[str],
    fotos_piezas: dict[str, str],
) -> dict[str, Any]:
    """`fotos_huecos`: hueco -> data URI. `conceptuales`: huecos cuya imagen es un render con IA.
    `fotos_piezas`: id de imagen -> data URI."""
    parametros = config.parametros
    tipografia = parametros.tipografia_titulos
    escala = parametros.escala_titulos
    ancho_util = ANCHO_PAGINA - 2 * MARGEN
    grupos = {g.clave: g for g in agrupar_por_seccion(detalle)}
    dinero = dinero_de(config)
    traducir = traductor_de(config)
    t = idiomas.etiquetas_de(config.idioma)

    secciones = []
    for vista in vistas:
        if not vista.incluir or vista.clave not in grupos:
            continue
        piezas = [_pieza(i, fotos_piezas, dinero, traducir) for i in grupos[vista.clave].items]
        hueco = hueco_montaje(vista.clave)
        titulo = traducir(vista.titulo)
        respaldo = [
            f"{formatear_cantidad(vista.piezas)} {t['piezas']}.",
            "\n".join(p.nombre.capitalize() for p in piezas[:5]),
            traducir("En Minimal 4.0 cuidamos que cada pieza mantenga el estilo de tu evento."),
        ]
        secciones.append(
            {
                "titulo": titulo,
                "tamano_titulo": tamano_titulo(titulo, ancho_util, 170 * escala, tipografia),
                "columnas": [traducir(c) for c in _columnas(vista.texto, respaldo)],
                "montaje": fotos_huecos.get(hueco),
                "montaje_conceptual": hueco in conceptuales,
                "portada_pieza": next((p.foto for p in piezas if p.foto), None),
                "paginas": _paginas_de_piezas(piezas, parametros.piezas_por_pagina),
            }
        )

    fondo = parametros.paleta.fondo
    identificador = CREMA if es_oscuro(fondo) else NEGRO
    concentrado = [
        {
            "titulo": traducir(v.titulo),
            "partidas": v.partidas,
            "piezas": formatear_cantidad(v.piezas),
            "importe": dinero(v.importe),
        }
        for v in vistas
    ]
    totales: list[tuple[str, str]] = [(t["subtotal_mobiliario"], dinero(detalle.subtotal))]
    hay_flete = any(i.cargo == "flete" for i in detalle.items)
    hay_montaje = any(i.cargo == "montaje" for i in detalle.items)
    if hay_flete:
        totales.append((t["flete"], dinero(detalle.flete)))
    if hay_montaje:
        totales.append((t["montaje"], dinero(detalle.montaje)))
    if detalle.iva is not None:
        totales.append((t["iva"], dinero(detalle.iva)))

    hoy = datetime.now(ZoneInfo("America/Merida"))
    titulo_portada = traducir(config.titulo.strip() or "PROPUESTA DE MOBILIARIO")
    titulo_concentrado = t["inversion"] if config.mostrar_precios else t["resumen"]
    return {
        "config": config,
        "parametros": parametros,
        "paleta": parametros.paleta,
        "t": t,
        "idioma": config.idioma,
        "fuente_titulos": '"Bebas Neue", sans-serif' if tipografia == "bebas" else '"Everett", "Public Sans", sans-serif',
        "everett": {peso: ruta.as_uri() for peso, ruta in archivos_everett().items()},
        "dir_fuentes": DIR_FUENTES.as_uri(),
        "menta": MENTA,
        "linea": mezclar(parametros.paleta.texto, fondo, 0.78),
        "texto_suave": mezclar(parametros.paleta.texto, fondo, 0.42),
        "logotipo_menta": logo("logotipo", MENTA),
        "logotipo_identificador": logo("logotipo", identificador),
        "monograma": logo("monograma", identificador),
        "titulo_portada": titulo_portada,
        "tamano_portada": tamano_titulo(titulo_portada, ancho_util, 124 * escala, tipografia, lineas=2),
        "tamano_concentrado": tamano_titulo(titulo_concentrado, ancho_util, 150 * escala, tipografia),
        "titulo_concentrado": titulo_concentrado,
        "evento": traducir(config.evento.strip()),
        "fotos": fotos_huecos,
        "conceptuales": conceptuales,
        "manifiesto": [traducir(t_) for t_ in config.manifiesto if t_.strip()],
        "cierre": [traducir(t_) for t_ in config.cierre if t_.strip()],
        "secciones": secciones,
        "mostrar_precios": config.mostrar_precios,
        "concentrado": concentrado,
        "total_piezas": formatear_cantidad(sum(v.piezas for v in vistas)),
        "totales": totales,
        "total": dinero(detalle.total),
        "mas_iva": detalle.iva is None,
        "hay_flete": hay_flete,
        "hay_montaje": hay_montaje,
        "hay_conceptuales": bool(conceptuales),
        "nota_moneda": nota_moneda(config, t, hoy),
        "referencia": detalle.referencia_externa,
        "cliente": detalle.nombre_cliente,
        "fecha": hoy.strftime("%d/%m/%Y") if config.idioma == "es" else hoy.strftime("%m/%d/%Y"),
    }


def nota_moneda(config: ConfigPresentacion, t: dict[str, str], hoy: datetime) -> str:
    """Renglón al pie que dice en qué moneda están los importes (y a qué tipo de cambio)."""
    mas_iva = "_mas_iva" if config.mostrar_precios else ""
    if config.moneda == "USD" and config.tipo_cambio:
        fecha = hoy.strftime("%d/%m/%Y") if config.idioma == "es" else hoy.strftime("%m/%d/%Y")
        return t[f"precios_en_dolares{mas_iva}"].format(tipo_cambio=f"{config.tipo_cambio:,.2f}", fecha=fecha)
    return t[f"precios_en_pesos{mas_iva}"]


def _entorno() -> Environment:
    entorno = Environment(loader=FileSystemLoader(DIR_PLANTILLAS), autoescape=select_autoescape(["html", "xml"]))
    entorno.filters["renglones"] = lambda texto: [r for r in (texto or "").split("\n")]
    return entorno


def renderizar_html(contexto: dict[str, Any]) -> str:
    return _entorno().get_template(PLANTILLA).render(**contexto)


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

async def generar_pdf(
    detalle: CotizacionDetalle,
    config: ConfigPresentacion,
    vistas: list[SeccionVista],
    imagenes_huecos: dict[str, dict[str, Any]],
    storage: Any,
) -> bytes:
    """`imagenes_huecos`: hueco -> fila de `imagenes` (con ruta_storage y tipo)."""

    async def bajar(ruta: str, lado: int) -> str | None:
        try:
            datos = await storage.descargar(storage.bucket_imagenes, ruta)
            return await asyncio.to_thread(foto_a_data_uri, datos, lado)
        except HTTPException:
            return None  # ya no está en Storage: la página sale sin esa foto

    incluidas = {v.clave for v in vistas if v.incluir}
    fotos_items = {
        str(i.imagen.id): i.imagen.ruta_storage
        for i in detalle.items
        if i.imagen and not i.cargo and i.categoria in incluidas
    }
    huecos = list(imagenes_huecos.items())
    resultados = await asyncio.gather(
        *(bajar(fila["ruta_storage"], LADO_FOTO_GRANDE) for _, fila in huecos),
        *(bajar(ruta, LADO_FOTO_PIEZA) for ruta in fotos_items.values()),
    )
    fotos_huecos = {h: uri for (h, _), uri in zip(huecos, resultados[: len(huecos)]) if uri}
    fotos_piezas = {i: uri for i, uri in zip(fotos_items, resultados[len(huecos) :]) if uri}
    conceptuales = {h for h, fila in huecos if fila.get("tipo") in ("montaje", "generada") and h in fotos_huecos}

    html = renderizar_html(construir_contexto(detalle, config, vistas, fotos_huecos, conceptuales, fotos_piezas))
    return await asyncio.to_thread(html_a_pdf, html)
