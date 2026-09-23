"""Idioma y unidades de la propuesta: etiquetas fijas, medidas y glosario de respaldo.

Lo que se traduce con reglas (sin IA y sin costo):
  - Las etiquetas fijas de los dos PDF (Subtotal, Piezas, Total…).
  - Las medidas: el catálogo las guarda siempre en centímetros ("ancho 190 cm · largo 190 cm") y las
    descripciones del sistema mezclan centímetros ("270 X 120 CM") con metros, a veces sin unidad
    ("MESA REDONDA DE 1.80 DIAMETRO"). En inglés salen en pies y pulgadas.
  - Un glosario corto de mobiliario, que sólo se usa si la traducción con IA no está disponible.

Los textos libres (descripciones, títulos y frases del vendedor) los traduce `ia_texto.traducir`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from dataclasses import field as dc_field

Idioma = str  # 'es' | 'en'

# --- Moneda ------------------------------------------------------------------


@dataclass
class Dinero:
    """Formatea importes. En dólares divide entre el tipo de cambio que puso el vendedor."""

    moneda: str = "MXN"
    tipo_cambio: float | None = None

    @property
    def en_dolares(self) -> bool:
        return self.moneda == "USD" and bool(self.tipo_cambio)

    def __call__(self, valor: float | int) -> str:
        if self.en_dolares:
            return f"US${float(valor) / float(self.tipo_cambio or 1):,.2f}"
        return f"${float(valor):,.2f}"


# --- Traducción de textos libres ---------------------------------------------


@dataclass
class Traductor:
    """Aplica la traducción ya pagada (caché) y convierte las medidas a pies y pulgadas.

    Si un texto no está en la caché usa el glosario, para que el PDF nunca salga a medias.
    """

    idioma: str = "es"
    cache: dict[str, str] = dc_field(default_factory=dict)

    @property
    def traduce(self) -> bool:
        return self.idioma != "es"

    def __call__(self, texto: str) -> str:
        if not self.traduce or not texto:
            return texto
        return convertir_medidas(self.cache.get(texto) or traducir_glosario(texto))

    def medidas(self, texto: str) -> str:
        """Las medidas del catálogo, con sus etiquetas traducidas."""
        if not self.traduce or not texto:
            return texto
        return traducir_medidas(self.cache.get(texto, texto), self.idioma)


# --- Etiquetas fijas ---------------------------------------------------------

ETIQUETAS: dict[str, dict[str, str]] = {
    "es": {
        "propuesta_de_mobiliario": "Propuesta de mobiliario",
        "lema_marca": "Minimal 4.0 · Diseño, construcción y eventos",
        "cliente": "Cliente",
        "referencia": "Referencia",
        "cotizacion": "Cotización",
        "fecha": "Fecha",
        "imagen": "Imagen",
        "descripcion": "Descripción",
        "cantidad_corta": "Cant.",
        "precio_unitario": "P. unitario",
        "importe": "Importe",
        "sin_imagen": "Sin imagen",
        "codigo": "Código",
        "render_conceptual": "Render conceptual",
        "render_conceptual_ia": "Render conceptual · IA",
        "nota_render_item": "Imagen de referencia de acabado, sujeta a confirmación de producción.",
        "partida": "partida",
        "partidas": "partidas",
        "pieza": "pieza",
        "piezas": "piezas",
        "cada_uno": "c/u",
        "seccion": "Sección",
        "subtotal_mobiliario": "Subtotal mobiliario",
        "flete": "Flete",
        "montaje": "Montaje",
        "iva": "IVA",
        "total": "Total",
        "mas_iva": "(más IVA)",
        "inversion": "Inversión",
        "resumen": "Resumen",
        "total_piezas": "Total de piezas",
        "mobiliario": "Mobiliario",
        "propuesta": "Propuesta",
        "pagina": "Página",
        "de": "de",
        "leyenda_render_titulo": "Sobre los renders conceptuales.",
        "leyenda_render": (
            'Las imágenes marcadas como "Render conceptual" son una referencia visual del acabado '
            "solicitado, generada a partir de la fotografía de la pieza original. El color, la textura y "
            "el resultado final están sujetos a confirmación de producción."
        ),
        "nota_conceptuales": (
            "Las imágenes marcadas como render conceptual se generaron con IA para ilustrar el montaje; "
            "el mobiliario y el espacio reales pueden variar."
        ),
        "considera_flete": "La propuesta considera flete.",
        "considera_montaje": "La propuesta considera montaje.",
        "considera_flete_montaje": "La propuesta considera flete y montaje.",
        "pie_informativo": (
            "Esta propuesta es informativa y no sustituye la cotización formal emitida por el sistema de "
            "la empresa."
        ),
        "precios_en_pesos": "Precios en pesos mexicanos.",
        "precios_en_pesos_mas_iva": "Precios en pesos mexicanos, más IVA.",
        # {tipo_cambio} y {fecha} se rellenan al armar la nota.
        "precios_en_dolares": (
            "Importes en dólares estadounidenses, convertidos a {tipo_cambio} pesos por dólar "
            "({fecha}). La cotización formal se emite en pesos."
        ),
        "precios_en_dolares_mas_iva": (
            "Importes en dólares estadounidenses, más IVA, convertidos a {tipo_cambio} pesos por dólar "
            "({fecha}). La cotización formal se emite en pesos."
        ),
        # Etiquetas de las medidas del catálogo.
        "ancho": "ancho",
        "largo": "largo",
        "alto": "alto",
        "respaldo": "respaldo",
        "base respaldo": "base respaldo",
        "asiento": "asiento",
        "diametro": "diámetro",
    },
    "en": {
        "propuesta_de_mobiliario": "Furniture proposal",
        "lema_marca": "Minimal 4.0 · Design, production and events",
        "cliente": "Client",
        "referencia": "Reference",
        "cotizacion": "Quote",
        "fecha": "Date",
        "imagen": "Image",
        "descripcion": "Description",
        "cantidad_corta": "Qty",
        "precio_unitario": "Unit price",
        "importe": "Amount",
        "sin_imagen": "No image",
        "codigo": "Code",
        "render_conceptual": "Concept render",
        "render_conceptual_ia": "Concept render · AI",
        "nota_render_item": "Finish reference image, subject to production confirmation.",
        "partida": "line",
        "partidas": "lines",
        "pieza": "piece",
        "piezas": "pieces",
        "cada_uno": "each",
        "seccion": "Section",
        "subtotal_mobiliario": "Furniture subtotal",
        "flete": "Freight",
        "montaje": "Setup",
        "iva": "VAT",
        "total": "Total",
        "mas_iva": "(plus VAT)",
        "inversion": "Investment",
        "resumen": "Summary",
        "total_piezas": "Total pieces",
        "mobiliario": "Furniture",
        "propuesta": "Proposal",
        "pagina": "Page",
        "de": "of",
        "leyenda_render_titulo": "About the concept renders.",
        "leyenda_render": (
            'Images marked "Concept render" are a visual reference of the requested finish, generated '
            "from a photograph of the original piece. Color, texture and final result are subject to "
            "production confirmation."
        ),
        "nota_conceptuales": (
            "Images marked as concept renders were generated with AI to illustrate the setup; the actual "
            "furniture and venue may differ."
        ),
        "considera_flete": "This proposal includes freight.",
        "considera_montaje": "This proposal includes setup.",
        "considera_flete_montaje": "This proposal includes freight and setup.",
        "pie_informativo": (
            "This proposal is informative and does not replace the formal quote issued by the company's "
            "system."
        ),
        "precios_en_pesos": "Prices in Mexican pesos.",
        "precios_en_pesos_mas_iva": "Prices in Mexican pesos, plus VAT.",
        "precios_en_dolares": (
            "Amounts in US dollars, converted at {tipo_cambio} pesos per dollar ({fecha}). The formal "
            "quote is issued in pesos."
        ),
        "precios_en_dolares_mas_iva": (
            "Amounts in US dollars, plus VAT, converted at {tipo_cambio} pesos per dollar ({fecha}). The "
            "formal quote is issued in pesos."
        ),
        "ancho": "width",
        "largo": "length",
        "alto": "height",
        "respaldo": "back",
        "base respaldo": "back height",
        "asiento": "seat",
        "diametro": "diameter",
    },
}


def etiqueta(idioma: Idioma, clave: str) -> str:
    """Etiqueta fija en el idioma pedido; si falta, la de español (nunca revienta un PDF)."""
    return ETIQUETAS.get(idioma, ETIQUETAS["es"]).get(clave) or ETIQUETAS["es"].get(clave, clave)


def etiquetas_de(idioma: Idioma) -> dict[str, str]:
    """Diccionario completo para pasárselo a la plantilla como `t`."""
    return {**ETIQUETAS["es"], **ETIQUETAS.get(idioma, {})}


# --- Medidas -----------------------------------------------------------------

_PULGADAS_POR_METRO = 39.3700787


def pies_pulgadas(metros: float) -> str:
    """0.75 m -> 2'6\"; 0.45 m -> 18\". Redondeo a la pulgada, que es como se cotiza allá."""
    pulgadas = round(metros * _PULGADAS_POR_METRO)
    pies, resto = divmod(pulgadas, 12)
    if pies == 0:
        return f'{resto}"'
    return f"{pies}'" if resto == 0 else f'{pies}\'{resto}"'


def _numero(texto: str) -> float:
    return float(texto.replace(",", "."))


# "270 X 120 CM", "45 × 43 cm"
_PAR_CM = re.compile(r"(\d+(?:[.,]\d+)?)\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*(?:cm|cms|centímetros?|centimetros?)\b", re.I)
# "6 X 4 M", "2.4 x 1.2 mts"
_PAR_M = re.compile(r"(\d+(?:[.,]\d+)?)\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*(?:m|mt|mts|metros?)\b", re.I)
_CM = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:cm|cms|centímetros?|centimetros?)\b", re.I)
_M = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:m|mt|mts|metros?)\b", re.I)
# Decimal sin unidad: en este catálogo son metros ("MESA LIENZO CURVA 2.40", "REDONDA DE 1.80").
_DECIMAL_SUELTO = re.compile(r"(?<![\d.,$])(\d{1,2}[.,]\d{1,2})(?![\d.,]*\s*(?:%|cm|mm|kg|pax|pz))", re.I)


def convertir_medidas(texto: str) -> str:
    """Pasa a pies y pulgadas las medidas que trae el texto. Sólo se llama cuando el idioma no es español."""
    if not texto:
        return texto
    convertido = _PAR_CM.sub(lambda m: f"{pies_pulgadas(_numero(m[1]) / 100)} x {pies_pulgadas(_numero(m[2]) / 100)}", texto)
    convertido = _PAR_M.sub(lambda m: f"{pies_pulgadas(_numero(m[1]))} x {pies_pulgadas(_numero(m[2]))}", convertido)
    convertido = _CM.sub(lambda m: pies_pulgadas(_numero(m[1]) / 100), convertido)
    convertido = _M.sub(lambda m: pies_pulgadas(_numero(m[1])), convertido)
    convertido = _DECIMAL_SUELTO.sub(lambda m: pies_pulgadas(_numero(m[1])), convertido)
    return convertido


_ETIQUETAS_MEDIDAS = ("base respaldo", "respaldo", "asiento", "ancho", "largo", "alto", "diámetro", "diametro")


def traducir_medidas(medidas: str, idioma: Idioma) -> str:
    """Las medidas del catálogo: "ancho 190 cm · alto 75 cm" -> "width 6'3\" · height 2'6\""."""
    if not medidas or idioma == "es":
        return medidas
    texto = convertir_medidas(medidas)
    for etiqueta_es in _ETIQUETAS_MEDIDAS:
        texto = re.sub(rf"\b{etiqueta_es}\b", etiqueta(idioma, etiqueta_es.replace("á", "a")), texto, flags=re.I)
    return texto


# --- Glosario de respaldo ----------------------------------------------------
# Sólo entra si la traducción con IA no está disponible: deja el texto legible aunque incompleto.

GLOSARIO: dict[str, str] = {
    "silla": "chair", "sillas": "chairs", "sillon": "armchair", "sillón": "armchair",
    "mesa": "table", "mesas": "tables", "mesita": "side table", "periquera": "cocktail table",
    "banco": "stool", "bancos": "stools", "banca": "bench", "barra": "bar", "contrabarra": "back bar",
    "mantel": "tablecloth", "manteles": "tablecloths", "funda": "cover", "fundas": "covers",
    "tarima": "stage", "tarimas": "stages", "pergola": "pergola", "pérgola": "pergola",
    "lampara": "lamp", "lámpara": "lamp", "lamparas": "lamps", "lámparas": "lamps",
    "sala": "lounge set", "lounge": "lounge", "puff": "ottoman", "cojin": "cushion", "cojín": "cushion",
    "centro de mesa": "centerpiece", "florero": "vase", "candelabro": "candelabra", "vela": "candle",
    "letrero": "sign", "cortina": "curtain", "cortinas": "curtains", "tapete": "rug", "alfombra": "carpet",
    "estante": "shelf", "estanteria": "shelving", "estantería": "shelving", "librero": "bookcase",
    "redonda": "round", "rectangular": "rectangular", "cuadrada": "square", "ovalada": "oval",
    "alta": "tall", "alto": "tall", "baja": "low", "bajo": "low", "grande": "large", "chica": "small",
    "blanca": "white", "blanco": "white", "negra": "black", "negro": "black", "dorada": "gold",
    "dorado": "gold", "plateada": "silver", "natural": "natural", "madera": "wood", "cristal": "glass",
    "metal": "metal", "ratan": "rattan", "ratán": "rattan", "lino": "linen", "terciopelo": "velvet",
    "crudo": "raw", "beige": "beige", "arena": "sand", "chocolate": "chocolate", "verde": "green",
    "azul": "blue", "rojo": "red", "gris": "grey", "incluye": "includes", "con": "with", "sin": "without",
    "de": "of", "para": "for", "y": "and", "moño": "bow", "diametro": "diameter", "diámetro": "diameter",
    "forrada": "covered", "forrado": "covered", "personalizado": "custom", "personalizada": "custom",
    "flete": "freight", "montaje": "setup", "desmontaje": "teardown", "traslado": "transport",
}

_PALABRA = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+(?:\s+[a-záéíóúüñ]+)?")


def traducir_glosario(texto: str) -> str:
    """Cambia las palabras que están en el glosario, respetando mayúsculas. Lo demás queda igual."""
    if not texto:
        return texto

    def cambiar(coincidencia: re.Match[str]) -> str:
        original = coincidencia.group(0)
        traduccion = GLOSARIO.get(original.lower())
        if traduccion is None:
            return original
        if original.isupper():
            return traduccion.upper()
        if original[:1].isupper():
            return traduccion.capitalize()
        return traduccion

    # Primero las expresiones de dos palabras (centro de mesa), después las sueltas.
    compuestas = sorted((c for c in GLOSARIO if " " in c), key=len, reverse=True)
    for compuesta in compuestas:
        texto = re.sub(rf"\b{re.escape(compuesta)}\b", lambda m: cambiar(m), texto, flags=re.I)
    return _PALABRA.sub(lambda m: cambiar(m) if " " not in m.group(0) else m.group(0), texto)


def traducir_con_reglas(texto: str, idioma: Idioma) -> str:
    """Respaldo completo sin IA: glosario + medidas."""
    if idioma == "es":
        return texto
    return convertir_medidas(traducir_glosario(texto))
