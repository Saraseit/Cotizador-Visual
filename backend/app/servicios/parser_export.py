"""Lectura del export del sistema de la empresa.

La estructura exacta del archivo real todavía no se conoce, por eso todo se lee a partir
de un mapeo configurable (`fixtures/mapeo_columnas.json`):

    {
      "formato": "xlsx",              # informativo; el formato real se decide por la extensión
      "hoja": 0,                      # índice o nombre de la hoja (xlsx)
      "fila_encabezados": 5,          # fila (1-based) donde están los encabezados de la tabla
      "columnas": {                   # campo interno -> encabezado tal como aparece en el archivo
        "codigo": "Código",
        "descripcion": "Descripción",
        "cantidad": "Cantidad",
        "precio_unitario": "Precio"
      },
      "metadatos": {                  # cómo obtener cliente y referencia
        "nombre_cliente":     {"celda": "B2", "regex": "Cliente:\\s*(.+)"},
        "referencia_externa": {"celda": "B3", "regex": "Referencia:\\s*(\\S+)"}
      },
      "pdf": {"estrategia": "auto"}   # auto | lineas | texto (ver _extraer_tablas_pdf)
    }

  - En .xlsx los metadatos se leen de `celda`; si no hay celda (o está vacía) se intenta `regex`
    sobre el texto de las primeras filas.
  - En .pdf sólo aplica `regex` sobre el texto extraído. Las tablas se extraen con pdfplumber:
    primero con la estrategia de líneas (tablas con bordes) y, si no encuentra ninguna, por
    alineación de texto. El encabezado se busca en cualquier fila de la tabla.

PUNTO DE EXTENSIÓN (PDF): si con el export real ninguna estrategia detecta la tabla, ajusta
`_extraer_tablas_pdf` (recortes de página, líneas explícitas, etc.). Está aislado a propósito.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
from typing import Any

import openpyxl

CAMPOS_OBLIGATORIOS = ("codigo", "descripcion", "cantidad", "precio_unitario")
_FILAS_RESUMEN = re.compile(r"^(sub)?total\b|^iva\b|^impuesto", re.IGNORECASE)


class ErrorParser(ValueError):
    """El archivo no se pudo interpretar con el mapeo actual."""


@dataclass
class FilaExport:
    orden: int
    codigo: str
    descripcion: str
    cantidad: Decimal
    precio_unitario: Decimal


@dataclass
class ExportLeido:
    nombre_cliente: str
    referencia_externa: str
    filas: list[FilaExport]
    advertencias: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def cargar_mapeo(ruta: str | Path) -> dict[str, Any]:
    with open(ruta, encoding="utf-8") as archivo:
        mapeo = json.load(archivo)
    faltan = [c for c in CAMPOS_OBLIGATORIOS if c not in mapeo.get("columnas", {})]
    if faltan:
        raise ErrorParser(f"El mapeo de columnas no define: {', '.join(faltan)}")
    return mapeo


def normalizar_texto(texto: Any) -> str:
    """Minúsculas, sin acentos, espacios colapsados. Para comparar encabezados."""
    if texto is None:
        return ""
    plano = unicodedata.normalize("NFKD", str(texto))
    sin_acentos = "".join(c for c in plano if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sin_acentos).strip().lower()


def a_decimal(valor: Any) -> Decimal:
    """Convierte celdas numéricas o texto tipo '$1,234.50' / '1.234,50' a Decimal. Vacío -> 0."""
    if valor is None or valor == "":
        return Decimal("0")
    if isinstance(valor, bool):
        return Decimal(int(valor))
    if isinstance(valor, (int, float, Decimal)):
        return Decimal(str(valor))

    texto = re.sub(r"[^\d,.\-]", "", str(valor))
    if not texto or texto in {"-", ".", ","}:
        return Decimal("0")
    if "," in texto and "." in texto:
        # El último separador es el decimal; el otro son miles.
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        # Coma como decimal sólo si va seguida de 1-2 dígitos al final.
        if re.search(r",\d{1,2}$", texto):
            texto = texto.replace(",", ".")
        else:
            texto = texto.replace(",", "")
    try:
        return Decimal(texto)
    except InvalidOperation as error:
        raise ErrorParser(f"No se pudo interpretar el número '{valor}'") from error


def _celda_a_texto(valor: Any) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


def _resolver_columnas(encabezados: list[Any], columnas: dict[str, str]) -> dict[str, int]:
    """Devuelve {campo: índice de columna}. Compara sin acentos ni mayúsculas."""
    normalizados = [normalizar_texto(h) for h in encabezados]
    indices: dict[str, int] = {}
    for campo, nombre in columnas.items():
        objetivo = normalizar_texto(nombre)
        if not objetivo:
            continue
        if objetivo in normalizados:
            indices[campo] = normalizados.index(objetivo)
            continue
        parciales = [i for i, h in enumerate(normalizados) if h and (objetivo in h or h in objetivo)]
        if parciales:
            indices[campo] = parciales[0]

    faltan = [c for c in CAMPOS_OBLIGATORIOS if c not in indices]
    if faltan:
        visibles = [str(h) for h in encabezados if h not in (None, "")]
        raise ErrorParser(
            f"No se encontraron las columnas {faltan} en los encabezados {visibles}. "
            "Revisa fixtures/mapeo_columnas.json."
        )
    return indices


def _filas_desde_tabla(
    filas_crudas: list[list[Any]], indices: dict[str, int], advertencias: list[str]
) -> list[FilaExport]:
    filas: list[FilaExport] = []

    def valor(fila: list[Any], campo: str) -> Any:
        i = indices[campo]
        return fila[i] if i < len(fila) else None

    for numero, fila in enumerate(filas_crudas, start=1):
        codigo = _celda_a_texto(valor(fila, "codigo"))
        descripcion = _celda_a_texto(valor(fila, "descripcion"))
        if not codigo and not descripcion:
            continue  # fila vacía
        if not codigo and _FILAS_RESUMEN.match(descripcion):
            advertencias.append(f"Se omitió la fila de resumen '{descripcion}'.")
            continue
        try:
            cantidad = a_decimal(valor(fila, "cantidad"))
            precio = a_decimal(valor(fila, "precio_unitario"))
        except ErrorParser as error:
            advertencias.append(f"Fila {numero} ('{descripcion or codigo}'): {error}. Se usó 0.")
            cantidad, precio = Decimal("0"), Decimal("0")
        filas.append(
            FilaExport(
                orden=len(filas),
                codigo=codigo,
                descripcion=descripcion or codigo,
                cantidad=cantidad if cantidad > 0 else Decimal("1"),
                precio_unitario=precio,
            )
        )
    return filas


def _metadato_por_regex(texto: str, patron: str | None) -> str:
    if not patron:
        return ""
    coincidencia = re.search(patron, texto, re.IGNORECASE | re.MULTILINE)
    if not coincidencia:
        return ""
    grupo = coincidencia.group(1) if coincidencia.groups() else coincidencia.group(0)
    return grupo.strip()


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def leer_export(contenido: bytes, nombre_archivo: str, mapeo: dict[str, Any]) -> ExportLeido:
    extension = Path(nombre_archivo or "").suffix.lower()
    if extension in {".xlsx", ".xlsm"}:
        return leer_xlsx(contenido, mapeo)
    if extension == ".pdf":
        return leer_pdf(contenido, mapeo)
    raise ErrorParser(f"Formato no soportado '{extension or '(sin extensión)'}'. Sube un .xlsx o .pdf.")


# ---------------------------------------------------------------------------
# XLSX
# ---------------------------------------------------------------------------

def leer_xlsx(contenido: bytes, mapeo: dict[str, Any]) -> ExportLeido:
    try:
        libro = openpyxl.load_workbook(BytesIO(contenido), data_only=True)
    except Exception as error:  # openpyxl lanza varios tipos distintos
        raise ErrorParser(f"No se pudo abrir el archivo de Excel: {error}") from error

    hoja_ref = mapeo.get("hoja", 0)
    try:
        hoja = libro.worksheets[int(hoja_ref)] if isinstance(hoja_ref, int) or str(hoja_ref).isdigit() else libro[hoja_ref]
    except (IndexError, KeyError) as error:
        raise ErrorParser(f"La hoja '{hoja_ref}' no existe en el archivo.") from error

    filas = [list(fila) for fila in hoja.iter_rows(values_only=True)]
    fila_encabezados = int(mapeo.get("fila_encabezados", 1))
    if len(filas) < fila_encabezados:
        raise ErrorParser(f"El archivo tiene menos de {fila_encabezados} filas; no se encontraron encabezados.")

    indices = _resolver_columnas(filas[fila_encabezados - 1], mapeo["columnas"])
    advertencias: list[str] = []
    items = _filas_desde_tabla(filas[fila_encabezados:], indices, advertencias)

    texto_cabecera = "\n".join(
        " ".join(_celda_a_texto(c) for c in fila if c not in (None, ""))
        for fila in filas[: fila_encabezados - 1]
    )
    metadatos = _leer_metadatos_xlsx(hoja, texto_cabecera, mapeo.get("metadatos", {}))

    return ExportLeido(
        nombre_cliente=metadatos.get("nombre_cliente", ""),
        referencia_externa=metadatos.get("referencia_externa", ""),
        filas=items,
        advertencias=advertencias,
    )


def _leer_metadatos_xlsx(hoja: Any, texto_cabecera: str, especificacion: dict[str, Any]) -> dict[str, str]:
    resultado: dict[str, str] = {}
    for campo, spec in especificacion.items():
        valor = ""
        celda = spec.get("celda")
        if celda:
            try:
                valor = _celda_a_texto(hoja[celda].value)
            except (ValueError, KeyError):
                valor = ""
        if not valor:
            valor = _metadato_por_regex(texto_cabecera, spec.get("regex"))
        resultado[campo] = valor
    return resultado


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

# Ajustes de pdfplumber para tablas sin líneas dibujadas: detecta columnas por la alineación del texto.
AJUSTES_PDF_TEXTO = {"vertical_strategy": "text", "horizontal_strategy": "text"}
ESTRATEGIAS_PDF = {"auto": ("lineas", "texto"), "lineas": ("lineas",), "texto": ("texto",)}


def _extraer_tablas_pdf(contenido: bytes, estrategia: str = "auto") -> tuple[list[list[list[Any]]], str, str]:
    """Devuelve (tablas, texto completo, estrategia que encontró tablas).

    Estrategias de pdfplumber:
      - "lineas": la de por defecto; necesita bordes dibujados en la tabla.
      - "texto":  columnas por alineación del texto; para exports sin bordes.
      - "auto":   prueba "lineas" y, si no encuentra ninguna tabla, reintenta con "texto".

    Se fuerza una desde el mapeo con `"pdf": {"estrategia": "lineas" | "texto"}` en
    fixtures/mapeo_columnas.json. Si con el archivo real ninguna funciona, este es el punto
    donde ajustar (recortes de página, `explicit_vertical_lines`, etc.).
    """
    import pdfplumber

    orden = ESTRATEGIAS_PDF.get(estrategia)
    if orden is None:
        raise ErrorParser(f"Estrategia de PDF desconocida '{estrategia}'. Usa 'auto', 'lineas' o 'texto'.")

    with pdfplumber.open(BytesIO(contenido)) as pdf:
        texto = "\n".join(pagina.extract_text() or "" for pagina in pdf.pages)
        for nombre in orden:
            tablas: list[list[list[Any]]] = []
            for pagina in pdf.pages:
                encontradas = pagina.extract_tables(AJUSTES_PDF_TEXTO) if nombre == "texto" else pagina.extract_tables()
                for tabla in encontradas:
                    if tabla and len(tabla) >= 2:
                        tablas.append([[c if c is not None else "" for c in fila] for fila in tabla])
            if tablas:
                return tablas, texto, nombre
    return [], texto, orden[-1]


def _limpiar_fila_pdf(fila: list[Any]) -> list[str]:
    return [str(c).replace("\n", " ").strip() if c is not None else "" for c in fila]


def leer_pdf(contenido: bytes, mapeo: dict[str, Any]) -> ExportLeido:
    estrategia = str((mapeo.get("pdf") or {}).get("estrategia", "auto"))
    try:
        tablas, texto, usada = _extraer_tablas_pdf(contenido, estrategia)
    except ErrorParser:
        raise
    except Exception as error:
        raise ErrorParser(f"No se pudo leer el PDF: {error}") from error
    if not tablas:
        raise ErrorParser(
            "No se detectaron tablas en el PDF (estrategia '" + usada + "'). "
            "Prueba con \"pdf\": {\"estrategia\": \"texto\"} en el mapeo o ajusta _extraer_tablas_pdf."
        )

    columnas = mapeo["columnas"]
    indices: dict[str, int] | None = None
    encabezado_normalizado: list[str] = []
    filas_datos: list[list[Any]] = []
    for tabla in tablas:
        limpia = [_limpiar_fila_pdf(fila) for fila in tabla]
        if indices is None:
            # El encabezado puede no ser la primera fila (con la estrategia por texto la tabla
            # suele arrastrar las líneas de cabecera del documento).
            for posicion, fila in enumerate(limpia):
                try:
                    indices = _resolver_columnas(fila, columnas)
                except ErrorParser:
                    continue
                encabezado_normalizado = [normalizar_texto(c) for c in fila]
                filas_datos.extend(limpia[posicion + 1 :])
                break
            continue
        # Tablas siguientes (otras páginas): se salta el encabezado repetido.
        for fila in limpia:
            if [normalizar_texto(c) for c in fila] == encabezado_normalizado:
                continue
            filas_datos.append(fila)

    if indices is None:
        raise ErrorParser(
            f"Ninguna tabla del PDF (estrategia '{usada}') tiene las columnas del mapeo. Revisa fixtures/mapeo_columnas.json."
        )

    advertencias: list[str] = [f"PDF leído con la estrategia '{usada}'."]
    items = _filas_desde_tabla(filas_datos, indices, advertencias)

    metadatos = {
        campo: _metadato_por_regex(texto, spec.get("regex"))
        for campo, spec in mapeo.get("metadatos", {}).items()
    }
    return ExportLeido(
        nombre_cliente=metadatos.get("nombre_cliente", ""),
        referencia_externa=metadatos.get("referencia_externa", ""),
        filas=items,
        advertencias=advertencias,
    )
