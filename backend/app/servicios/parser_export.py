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
      "pdf": {                        # ver leer_pdf
        "estrategia": "auto",         # auto | renglones | lineas | texto
        "encabezados": {"cantidad": "Cant.", "descripcion": "Artículo"},
        "codigo_en_descripcion": "<regex con un grupo>",
        "metadatos": {"nombre_cliente": {"etiqueta": "Cliente:"}, "referencia_externa": {"debajo_de": "Cotización"}}
      }
    }

  - En .xlsx los metadatos se leen de `celda`; si no hay celda (o está vacía) se intenta `regex`
    sobre el texto de las primeras filas.
  - En .pdf se usa la sección `pdf` del mapeo. La estrategia por defecto lee renglones (formato del
    sistema de la empresa: sin tabla dibujada, código dentro del artículo, "Reposición" bajo la
    cantidad); si no lo reconoce, prueba tablas por líneas y por texto con `columnas`.

PUNTO DE EXTENSIÓN (PDF): `_leer_pdf_por_renglones` para el formato del sistema y `_extraer_tablas_pdf`
para PDFs con tabla. Están aislados a propósito.
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
    # Sólo los trae el formato PDF por renglones; hoy no se guardan, sirven para validar.
    categoria: str = ""
    importe: Decimal | None = None
    costo_reposicion: Decimal | None = None
    # Posición del renglón en el PDF (página base 0 y `top` en pt): sirve para emparejar la foto de la partida.
    pagina: int | None = None
    top: float | None = None


@dataclass
class ExportLeido:
    nombre_cliente: str
    referencia_externa: str
    filas: list[FilaExport]
    advertencias: list[str] = field(default_factory=list)
    # IVA impreso en el PDF del sistema; None si el documento sólo dice "más IVA" (o es un .xlsx).
    iva: Decimal | None = None


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
ESTRATEGIAS_TABLA = {"auto": ("lineas", "texto"), "lineas": ("lineas",), "texto": ("texto",)}
ESTRATEGIAS_PDF = ("auto", "renglones", "lineas", "texto")

# Código al inicio del artículo: "1040 - MESA", "10081- MESA", "OC2050 - FUNDA", "SIL-001 - SILLA".
REGEX_CODIGO_POR_DEFECTO = r"^\s*([A-Za-z0-9.-]*\d[A-Za-z0-9.]*)\s*-\s*(?=\S)"
# Montos con signo de pesos: "$1,050.00". Sin el signo, "1.80" o "2.44" (medidas) se confundirían con montos.
_DINERO = re.compile(r"^\$-?[\d,]*\d(\.\d{1,2})?$")
_CANTIDAD = re.compile(r"^\d+(\.\d+)?$")
_PIE_PAGINA = re.compile(r"p[aá]gina\s+\d+\s+de\s+\d+", re.IGNORECASE)


def _config_pdf(mapeo: dict[str, Any]) -> dict[str, Any]:
    return mapeo.get("pdf") or {}


def _clave(texto: str) -> str:
    """'CANT.' -> 'cant', 'ARTÍCULO' -> 'articulo'. Para comparar encabezados y etiquetas."""
    return re.sub(r"[^a-z0-9]", "", normalizar_texto(texto))


def _agrupar_renglones(palabras: list[dict[str, Any]], tolerancia: float = 3.0) -> list[list[dict[str, Any]]]:
    renglones: list[list[dict[str, Any]]] = []
    for palabra in sorted(palabras, key=lambda w: (w["top"], w["x0"])):
        if renglones and abs(renglones[-1][0]["top"] - palabra["top"]) <= tolerancia:
            renglones[-1].append(palabra)
        else:
            renglones.append([palabra])
    return [sorted(r, key=lambda w: w["x0"]) for r in renglones]


def _texto(palabras: list[dict[str, Any]]) -> str:
    return " ".join(w["text"] for w in palabras).strip()


# --- Metadatos (cliente, referencia) -------------------------------------------

def _metadato_por_etiqueta(renglones: list[list[dict[str, Any]]], etiqueta: str) -> str:
    """Palabras a la derecha de la etiqueta en el mismo renglón, hasta la siguiente etiqueta ('Algo:') o un hueco grande."""
    objetivo = _clave(etiqueta)
    for renglon in renglones:
        for indice, palabra in enumerate(renglon):
            if _clave(palabra["text"]) != objetivo:
                continue
            valor: list[dict[str, Any]] = []
            anterior = palabra
            for siguiente in renglon[indice + 1 :]:
                if siguiente["text"].endswith(":") or siguiente["x0"] - anterior["x1"] > 60:
                    break
                valor.append(siguiente)
                anterior = siguiente
            if valor:
                return _texto(valor)
    return ""


def _metadato_debajo_de(renglones: list[list[dict[str, Any]]], etiqueta: str) -> str:
    """Primera palabra debajo de la etiqueta (hasta 45 pt), que se traslape horizontalmente con ella."""
    objetivo = _clave(etiqueta)
    for renglon in renglones:
        for palabra in renglon:
            if _clave(palabra["text"]) != objetivo:
                continue
            candidatas = [
                w
                for r in renglones
                for w in r
                if palabra["bottom"] < w["top"] <= palabra["bottom"] + 45
                and w["x1"] >= palabra["x0"] - 20
                and w["x0"] <= palabra["x1"] + 20
            ]
            if candidatas:
                return min(candidatas, key=lambda w: (w["top"], w["x0"]))["text"].strip()
    return ""


def _leer_metadatos_pdf(renglones: list[list[dict[str, Any]]], texto: str, especificacion: dict[str, Any]) -> dict[str, str]:
    """Cada campo prueba, en orden, `debajo_de`, `etiqueta` y `regex`; gana el primero con valor."""
    resultado: dict[str, str] = {}
    for campo, spec in especificacion.items():
        valor = ""
        if spec.get("debajo_de"):
            valor = _metadato_debajo_de(renglones, spec["debajo_de"])
        if not valor and spec.get("etiqueta"):
            valor = _metadato_por_etiqueta(renglones, spec["etiqueta"])
        if not valor and spec.get("regex"):
            valor = _metadato_por_regex(texto, spec["regex"])
        resultado[campo] = valor
    return resultado


# --- Estrategia "renglones": exports sin tabla dibujada, con el código dentro del artículo ---

def _separar_codigo(descripcion: str, patron: str) -> tuple[str, str]:
    coincidencia = re.match(patron, descripcion)
    if not coincidencia:
        return "", descripcion
    return coincidencia.group(1), descripcion[coincidencia.end() :].strip()


def _es_encabezado(renglon: list[dict[str, Any]], encabezados: dict[str, str]) -> bool:
    claves = {_clave(w["text"]) for w in renglon}
    necesarias = [_clave(encabezados[c]) for c in ("cantidad", "descripcion") if encabezados.get(c)]
    return bool(necesarias) and all(any(n and (n == c or c.startswith(n)) for c in claves) for n in necesarias)


def _buscar_iva(renglones: list[list[dict[str, Any]]]) -> Decimal | None:
    """IVA del bloque de totales: la palabra "IVA" seguida de un monto en el mismo renglón.

    Se detiene en las notas ("Notas:", "IMPORTANTE DE LEER"), donde "más IVA." no lleva monto.
    """
    for renglon in renglones:
        if _clave(renglon[0]["text"]) in {"notas", "importante"}:
            return None
        for indice, palabra in enumerate(renglon):
            if _clave(palabra["text"]) != "iva":
                continue
            monto = next((w for w in renglon[indice + 1 :] if _DINERO.match(w["text"])), None)
            if monto is not None:
                return a_decimal(monto["text"])
    return None


def _leer_pdf_por_renglones(
    paginas: list[list[list[dict[str, Any]]]], mapeo: dict[str, Any]
) -> tuple[list[FilaExport], list[str], Decimal | None] | None:
    """Lee exports cuyo cuerpo no es una tabla con bordes (como el del sistema de Minimal 4.0).

    Cada página: se busca el renglón de encabezados (`pdf.encabezados`, p. ej. "CANT." y "ARTÍCULO")
    y se leen los renglones de abajo:
      - partida:        cantidad a la izquierda + artículo + precio unitario e importe a la derecha;
      - continuación:   sólo texto en la columna del artículo (descripciones de varias líneas);
      - "Reposición":   etiqueta y monto bajo la cantidad (costo de reposición de la partida);
      - sección:        texto a la izquierda del artículo sin montos ("FUNDAS", "MESA BANQUETE");
      - "Total de …":   subtotal de sección, se ignora;
      - "SubTotal":     fin del cuerpo; se usa para validar la suma.
    El código va al inicio del artículo y se separa con `pdf.codigo_en_descripcion`.
    Devuelve None si no encuentra encabezados ni partidas (para probar otra estrategia).
    """
    config = _config_pdf(mapeo)
    encabezados = config.get("encabezados") or {"cantidad": "Cant.", "descripcion": "Artículo"}
    patron_codigo = config.get("codigo_en_descripcion") or REGEX_CODIGO_POR_DEFECTO

    cuerpo: list[list[dict[str, Any]]] = []
    for renglones in paginas:
        inicio = next((i for i, r in enumerate(renglones) if _es_encabezado(r, encabezados)), None)
        if inicio is None:
            continue
        cuerpo.extend(r for r in renglones[inicio + 1 :] if not _PIE_PAGINA.search(_texto(r)))
    if not cuerpo:
        return None

    def es_partida(renglon: list[dict[str, Any]]) -> bool:
        return len(renglon) >= 3 and bool(_CANTIDAD.match(renglon[0]["text"])) and bool(_DINERO.match(renglon[-1]["text"]))

    partidas = [r for r in cuerpo if es_partida(r)]
    if not partidas:
        return None
    # Columnas deducidas de las propias partidas (el encabezado no siempre está alineado con los datos).
    inicios_articulo = sorted(r[1]["x0"] for r in partidas if not _DINERO.match(r[1]["text"]))
    if not inicios_articulo:
        return None
    x_articulo = inicios_articulo[len(inicios_articulo) // 2]
    x_montos = min(w["x0"] for r in partidas for w in r[1:] if _DINERO.match(w["text"]))
    limite_izquierda = x_articulo - 12

    filas: list[FilaExport] = []
    advertencias: list[str] = []
    seccion = ""
    reposicion_pendiente = False
    subtotal: Decimal | None = None
    iva: Decimal | None = None

    def continuar(palabras: list[dict[str, Any]]) -> None:
        if palabras and filas:
            filas[-1].descripcion = f"{filas[-1].descripcion} {_texto(palabras)}".strip()

    for indice_renglon, renglon in enumerate(cuerpo):
        texto = _texto(renglon)
        clave_inicio = _clave(renglon[0]["text"])
        if "subtotal" in _clave(texto) or clave_inicio.startswith("importe"):
            # SubTotal e IVA pueden ir en el mismo renglón o en los siguientes: se toma el monto
            # que sigue a la palabra "SubTotal" (no el último, que podría ser el IVA).
            for i, palabra in enumerate(renglon):
                if "subtotal" in _clave(palabra["text"]):
                    monto = next((w for w in renglon[i + 1 :] if _DINERO.match(w["text"])), None)
                    if monto is not None:
                        subtotal = a_decimal(monto["text"])
                    break
            iva = _buscar_iva(cuerpo[indice_renglon:])
            break

        izquierda = [w for w in renglon if w["x0"] < limite_izquierda]
        articulo = [w for w in renglon if limite_izquierda <= w["x0"] < x_montos - 12]
        montos = [w for w in renglon if w["x0"] >= x_montos - 12 and _DINERO.match(w["text"])]

        if es_partida(renglon) and renglon[0]["x0"] < limite_izquierda:
            precio = a_decimal(montos[-2]["text"]) if len(montos) >= 2 else a_decimal(montos[-1]["text"])
            importe = a_decimal(montos[-1]["text"])
            cantidad = a_decimal(renglon[0]["text"])
            filas.append(
                FilaExport(
                    orden=len(filas),
                    codigo="",
                    descripcion=_texto(articulo),
                    cantidad=cantidad if cantidad > 0 else Decimal("1"),
                    precio_unitario=precio,
                    categoria=seccion,
                    importe=importe,
                    pagina=renglon[0].get("pagina"),
                    top=renglon[0]["top"],
                )
            )
            reposicion_pendiente = False
            continue

        if izquierda and _clave(izquierda[0]["text"]).startswith("reposici"):
            reposicion_pendiente = True
            continuar(articulo)
            continue

        if izquierda and _DINERO.match(izquierda[0]["text"]):
            if reposicion_pendiente and filas:
                filas[-1].costo_reposicion = a_decimal(izquierda[0]["text"])
            reposicion_pendiente = False
            continuar(articulo)
            continue

        if _clave(_texto(articulo)).startswith("totalde"):
            continue

        if izquierda and not montos:
            seccion = texto
            continue

        if articulo and not izquierda and not montos:
            continuar(articulo)
            continue

        advertencias.append(f"Renglón no interpretado: '{texto[:80]}'.")

    # Código dentro del artículo, una vez que la descripción está completa.
    for fila in filas:
        fila.codigo, fila.descripcion = _separar_codigo(fila.descripcion, patron_codigo)
        if fila.importe is not None and abs(fila.cantidad * fila.precio_unitario - fila.importe) > Decimal("0.05"):
            advertencias.append(
                f"'{fila.codigo or fila.descripcion[:30]}': {fila.cantidad} × {fila.precio_unitario} no da el importe {fila.importe}."
            )

    if subtotal is not None:
        suma = sum((f.importe if f.importe is not None else f.cantidad * f.precio_unitario) for f in filas)
        if abs(suma - subtotal) > Decimal("0.5"):
            advertencias.append(f"La suma de partidas ({suma}) no coincide con el SubTotal del documento ({subtotal}).")
    return filas, advertencias, iva


# --- Estrategias de tabla ("lineas" y "texto") -----------------------------------

def _extraer_tablas_pdf(pdf: Any, estrategia: str) -> tuple[list[list[list[Any]]], str]:
    """Devuelve (tablas, estrategia que encontró tablas).

    - "lineas": la de pdfplumber por defecto; necesita bordes dibujados en la tabla.
    - "texto":  columnas por alineación del texto; para tablas sin bordes.
    - "auto":   prueba "lineas" y, si no encuentra ninguna tabla, "texto".
    """
    orden = ESTRATEGIAS_TABLA.get(estrategia, ESTRATEGIAS_TABLA["auto"])
    for nombre in orden:
        tablas: list[list[list[Any]]] = []
        for pagina in pdf.pages:
            encontradas = pagina.extract_tables(AJUSTES_PDF_TEXTO) if nombre == "texto" else pagina.extract_tables()
            for tabla in encontradas:
                if tabla and len(tabla) >= 2:
                    tablas.append([[c if c is not None else "" for c in fila] for fila in tabla])
        if tablas:
            return tablas, nombre
    return [], orden[-1]


def _limpiar_fila_pdf(fila: list[Any]) -> list[str]:
    return [str(c).replace("\n", " ").strip() if c is not None else "" for c in fila]


def _filas_de_tablas(tablas: list[list[list[Any]]], columnas: dict[str, str], advertencias: list[str]) -> list[FilaExport] | None:
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
        return None
    return _filas_desde_tabla(filas_datos, indices, advertencias)


# --- Punto de entrada PDF --------------------------------------------------------

def leer_pdf(contenido: bytes, mapeo: dict[str, Any]) -> ExportLeido:
    """Lee un export en PDF. Estrategias (`pdf.estrategia` en el mapeo):

      - "auto" (por defecto): "renglones" y, si no reconoce el formato, tablas por líneas y luego por texto;
      - "renglones": exports sin tabla dibujada con el código dentro del artículo (formato del sistema actual);
      - "lineas" / "texto": tablas con columnas `columnas` del mapeo (Código, Descripción, Cantidad, Precio).
    """
    import pdfplumber

    config = _config_pdf(mapeo)
    estrategia = str(config.get("estrategia", "auto"))
    if estrategia not in ESTRATEGIAS_PDF:
        raise ErrorParser(f"Estrategia de PDF desconocida '{estrategia}'. Usa 'auto', 'renglones', 'lineas' o 'texto'.")

    try:
        pdf = pdfplumber.open(BytesIO(contenido))
    except Exception as error:
        raise ErrorParser(f"No se pudo abrir el PDF: {error}") from error

    with pdf:
        try:
            paginas = []
            for numero, pagina in enumerate(pdf.pages):
                palabras = pagina.extract_words()
                for palabra in palabras:
                    palabra["pagina"] = numero
                paginas.append(_agrupar_renglones(palabras))
            texto = "\n".join(p.extract_text() or "" for p in pdf.pages)
        except Exception as error:
            raise ErrorParser(f"No se pudo leer el PDF: {error}") from error
        if not any(paginas):
            raise ErrorParser("El PDF no tiene texto seleccionable (¿es una imagen escaneada?).")

        filas: list[FilaExport] | None = None
        advertencias: list[str] = []
        iva: Decimal | None = None
        usada = ""
        if estrategia in ("auto", "renglones"):
            resultado = _leer_pdf_por_renglones(paginas, mapeo)
            if resultado is not None:
                filas, advertencias, iva = resultado
                usada = "renglones"
            elif estrategia == "renglones":
                raise ErrorParser(
                    "No se reconoció el formato por renglones: no se encontraron los encabezados "
                    f"{list((config.get('encabezados') or {}).values())} o ninguna partida con cantidad y montos."
                )
        if filas is None:
            try:
                tablas, usada = _extraer_tablas_pdf(pdf, "auto" if estrategia in ("auto", "renglones") else estrategia)
            except Exception as error:
                raise ErrorParser(f"No se pudo leer el PDF: {error}") from error
            filas = _filas_de_tablas(tablas, mapeo["columnas"], advertencias) if tablas else None
            if filas is None:
                raise ErrorParser(
                    "No se reconoció el formato del PDF: no hay renglones con los encabezados "
                    f"{list((config.get('encabezados') or {}).values())} ni tablas con las columnas "
                    f"{list(mapeo['columnas'].values())}. Revisa fixtures/mapeo_columnas.json."
                )

        especificacion = config.get("metadatos") or mapeo.get("metadatos", {})
        metadatos = _leer_metadatos_pdf(paginas[0] if paginas else [], texto, especificacion)

    advertencias.insert(0, f"PDF leído con la estrategia '{usada}'.")
    return ExportLeido(
        nombre_cliente=metadatos.get("nombre_cliente", ""),
        referencia_externa=metadatos.get("referencia_externa", ""),
        filas=filas,
        advertencias=advertencias,
        iva=iva,
    )
