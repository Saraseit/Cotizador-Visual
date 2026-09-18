"""Importa el reporte "EXISTENCIAS DE MATERIALES PARA ALQUILER" (PDF del sistema) al catálogo.

    python scripts/importar_inventario.py ruta/inventario.pdf                 # vista previa, no escribe
    python scripts/importar_inventario.py ruta/inventario.pdf --aplicar --lista "Público"

Formato que entiende: secciones ("SILLAS", "MESA BANQUETE"…) seguidas del renglón de encabezados
CODIGO | DESCRIPCION | EXISTENCIA | REPARACION | DIFERENCIA | REPO | PRECIO, un renglón por artículo y
descripciones largas continuadas en la línea de abajo.

Qué se carga por artículo:
  - código: el que va al inicio de la descripción ("2073- SILLA REBE"), porque es el que aparece en
    las cotizaciones; si no hay, el de la columna CODIGO. Las diferencias se reportan.
  - nombre: la descripción sin el código. categoría: la sección.
  - costo de reposición: REPO ($0.00 = sin dato). precio: PRECIO, en la lista indicada con --lista.
  - Las parejas REPO $1.00 / PRECIO $1.00 son marcadores del sistema y se tratan como sin dato.
  - Existencias no se guardan (el catálogo no las maneja).
  - Descripción, medidas y etiquetas quedan vacías para llenarse después.
Artículos sin ningún código: --sin-codigo provisional (código estable "SC-xxxxxx" derivado del
nombre, etiqueta "sin-codigo") u omitir.

Idempotente: upsert por código; un dato vacío en el PDF nunca borra lo que ya tenga el catálogo.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import re
import sys
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

RAIZ_BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_BACKEND))

from app.servicios.matching import normalizar_codigo  # noqa: E402
from app.servicios.parser_export import (  # noqa: E402
    REGEX_CODIGO_POR_DEFECTO,
    _agrupar_renglones,
    _clave,
    _DINERO,
    _separar_codigo,
    _texto,
    a_decimal,
    normalizar_texto,
)

# Conceptos internos del sistema que no son mobiliario: se cargan inactivos con etiqueta "interno".
CODIGOS_INTERNOS = {"000001", "00001", "00010", "01002", "31", "80", "86", "8029"}
_NUMERO = re.compile(r"^-?\d+(\.\d+)?$")
_CODIGO_OC_SIN_GUION = re.compile(r"^(OC)[\s-]+(\d{3,})\s+(.+)$", re.IGNORECASE)
MARCADOR = Decimal("1.00")


@dataclass
class Articulo:
    pagina: int
    seccion: str
    codigo_columna: str
    descripcion: str
    existencia: str
    reposicion: Decimal | None
    precio: Decimal | None
    codigo: str = ""
    nombre: str = ""
    avisos: list[str] = field(default_factory=list)
    interno: bool = False
    provisional: bool = False


# ---------------------------------------------------------------------------
# Lectura del PDF
# ---------------------------------------------------------------------------

def _es_encabezado(renglon: list[dict[str, Any]]) -> bool:
    claves = {_clave(w["text"]) for w in renglon}
    return "codigo" in claves and "descripcion" in claves


def leer_inventario(ruta: Path) -> tuple[list[Articulo], list[str]]:
    import pdfplumber

    articulos: list[Articulo] = []
    descartados: list[str] = []
    seccion = ""
    columnas: dict[str, float] | None = None

    with pdfplumber.open(ruta) as pdf:
        for numero_pagina, pagina in enumerate(pdf.pages, start=1):
            renglones = _agrupar_renglones(pagina.extract_words(), tolerancia=2)
            for indice, renglon in enumerate(renglones):
                if _es_encabezado(renglon):
                    # La sección es el renglón inmediatamente anterior al encabezado.
                    if indice > 0:
                        seccion = _texto(renglones[indice - 1])
                    x = {_clave(w["text"]): w["x0"] for w in renglon}
                    columnas = {
                        "descripcion": x["descripcion"] - 4,
                        "numeros": x.get("existencia", 340) - 12,
                        "montos": min(v for k, v in x.items() if k.startswith("repo")) - 15,
                    }
                    continue
                if columnas is None:
                    continue  # título y fecha del reporte

                montos = [w for w in renglon if w["x0"] >= columnas["montos"] and _DINERO.match(w["text"])]
                codigo_col = [w for w in renglon if w["x0"] < columnas["descripcion"]]
                desc = [w for w in renglon if columnas["descripcion"] <= w["x0"] < columnas["numeros"]]
                numeros = [w for w in renglon if columnas["numeros"] <= w["x0"] < columnas["montos"] and _NUMERO.match(w["text"])]

                if len(montos) >= 2 and len(numeros) >= 3:
                    texto_desc = _texto(desc)
                    if not texto_desc or texto_desc == ".":
                        descartados.append(f"pág. {numero_pagina} ({seccion}): renglón sin descripción '{_texto(renglon)}'")
                        continue
                    repo, precio = a_decimal(montos[-2]["text"]), a_decimal(montos[-1]["text"])
                    articulos.append(
                        Articulo(
                            pagina=numero_pagina,
                            seccion=seccion,
                            codigo_columna=_texto(codigo_col),
                            descripcion=texto_desc,
                            existencia=numeros[0]["text"],
                            reposicion=repo,
                            precio=precio,
                        )
                    )
                elif desc and not montos and not numeros and not codigo_col and articulos:
                    articulos[-1].descripcion = f"{articulos[-1].descripcion} {_texto(desc)}"
                elif _texto(renglon) != seccion:
                    # Título de la siguiente sección (se toma en el encabezado) u otra cosa.
                    siguiente = renglones[indice + 1] if indice + 1 < len(renglones) else None
                    if not (siguiente and _es_encabezado(siguiente)):
                        descartados.append(f"pág. {numero_pagina}: renglón no interpretado '{_texto(renglon)[:90]}'")
    return articulos, descartados


# ---------------------------------------------------------------------------
# Normalización
# ---------------------------------------------------------------------------

def _capitalizar(seccion: str) -> str:
    return seccion[:1].upper() + seccion[1:].lower() if seccion else ""


def _codigo_provisional(nombre: str) -> str:
    return "SC-" + hashlib.sha1(normalizar_texto(nombre).encode("utf-8")).hexdigest()[:6].upper()


def normalizar(articulos: list[Articulo], patron_codigo: str, sin_codigo: str) -> list[Articulo]:
    vistos: dict[str, Articulo] = {}
    resultado: list[Articulo] = []
    for a in articulos:
        codigo_desc, resto = _separar_codigo(a.descripcion, patron_codigo)
        columna = normalizar_codigo(a.codigo_columna)
        if not codigo_desc:
            oc = _CODIGO_OC_SIN_GUION.match(a.descripcion)
            if oc:
                codigo_desc, resto = f"{oc.group(1).upper()}{oc.group(2)}", oc.group(3)
                a.avisos.append(f"código tomado de '{a.descripcion.split()[0]} {a.descripcion.split()[1]}' (sin guion; en cotizaciones no se reconocerá solo)")
        codigo = normalizar_codigo(codigo_desc) or columna
        nombre = resto if codigo_desc else a.descripcion
        if codigo_desc and columna and normalizar_codigo(codigo_desc) != columna:
            a.avisos.append(f"columna CODIGO dice '{a.codigo_columna}', la descripción '{codigo_desc}'; se usa '{codigo_desc}'")
        if not codigo_desc and columna and nombre.upper().startswith(columna + " "):
            nombre = nombre[len(columna) :].strip()
        if not nombre or normalizar_codigo(nombre) == codigo:
            a.avisos.append("sin descripción en el inventario")
            nombre = codigo or a.descripcion

        if not codigo:
            if sin_codigo == "omitir":
                a.avisos.append("sin código: omitido")
                a.codigo = ""
                a.nombre = nombre
                resultado.append(a)
                continue
            codigo = _codigo_provisional(nombre)
            a.provisional = True

        # Marcadores del sistema y reposición en cero = sin dato.
        if a.reposicion == MARCADOR and a.precio == MARCADOR:
            a.reposicion, a.precio = None, None
            a.avisos.append("REPO y PRECIO en $1.00 (marcador): quedan sin dato")
        if a.reposicion is not None and a.reposicion == 0:
            a.reposicion = None

        a.codigo, a.nombre = codigo, nombre.strip()
        a.interno = codigo in CODIGOS_INTERNOS
        if codigo in vistos:
            a.avisos.append(f"código repetido (ya aparece en pág. {vistos[codigo].pagina}, '{vistos[codigo].nombre}'): se omite")
            a.codigo = ""
        else:
            vistos[codigo] = a
        resultado.append(a)
    return resultado


# ---------------------------------------------------------------------------
# Reporte
# ---------------------------------------------------------------------------

def reporte(articulos: list[Articulo], descartados: list[str], ruta_csv: Path) -> None:
    cargables = [a for a in articulos if a.codigo]
    secciones: dict[str, int] = {}
    for a in cargables:
        secciones[a.seccion] = secciones.get(a.seccion, 0) + 1

    print(f"Artículos leídos: {len(articulos)} | a cargar: {len(cargables)}")
    print(f"  con código: {sum(1 for a in cargables if not a.provisional)} | código provisional: {sum(1 for a in cargables if a.provisional)}"
          f" | internos (inactivos): {sum(1 for a in cargables if a.interno)} | omitidos: {len(articulos) - len(cargables)}")
    print(f"  con costo de reposición: {sum(1 for a in cargables if a.reposicion is not None)} | con precio: {sum(1 for a in cargables if a.precio is not None)}")
    print("Por sección:")
    for seccion, total in secciones.items():
        print(f"  {seccion:24} {total}")
    avisos = [a for a in articulos if a.avisos]
    print(f"Avisos ({len(avisos)}):")
    for a in avisos:
        print(f"  pág. {a.pagina:2} {a.codigo or '(omitido)':10} {a.nombre[:55]:55} | {'; '.join(a.avisos)}")
    for d in descartados:
        print(f"  descartado: {d}")

    ruta_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta_csv, "w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["codigo", "nombre", "categoria", "costo_reposicion", "precio", "existencia", "interno", "provisional", "avisos"])
        for a in articulos:
            escritor.writerow([a.codigo, a.nombre, _capitalizar(a.seccion), a.reposicion or "", "" if a.precio is None else a.precio,
                               a.existencia, "sí" if a.interno else "", "sí" if a.provisional else "", "; ".join(a.avisos)])
    print(f"\nVista previa completa en {ruta_csv}")


# ---------------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------------

async def aplicar(articulos: list[Articulo], nombre_lista: str, desactivar_ejemplo: bool) -> None:
    from app.config import obtener_configuracion
    from app.db.cliente import crear_cliente

    db = await crear_cliente(obtener_configuracion())
    cargables = [a for a in articulos if a.codigo]

    listas = (await db.table("listas_precios").select("*").execute()).data or []
    lista = next((l for l in listas if normalizar_texto(l["nombre"]) == normalizar_texto(nombre_lista)), None)
    if lista is None:
        lista = (await db.table("listas_precios").insert({"nombre": nombre_lista, "orden": len(listas) + 1}).execute()).data[0]
        print(f"Lista de precios creada: {nombre_lista}")

    existentes: dict[str, dict[str, Any]] = {}
    codigos = [a.codigo for a in cargables]
    for inicio in range(0, len(codigos), 200):
        lote = (await db.table("catalogo_items").select("*").in_("codigo", codigos[inicio : inicio + 200]).execute()).data or []
        existentes.update({f["codigo"]: f for f in lote})

    filas = []
    for a in cargables:
        base = existentes.get(a.codigo, {})
        etiquetas = set(base.get("etiquetas") or [])
        if a.interno:
            etiquetas.add("interno")
        if a.provisional:
            etiquetas.add("sin-codigo")
        costo = float(a.reposicion) if a.reposicion is not None else base.get("costo_reposicion")
        filas.append(
            {
                "codigo": a.codigo,
                "nombre": a.nombre or base.get("nombre") or a.codigo,
                "categoria": _capitalizar(a.seccion) or base.get("categoria") or "",
                "descripcion": base.get("descripcion") or "",
                "medidas": base.get("medidas") or "",
                "etiquetas": sorted(etiquetas),
                "costo_reposicion": costo,
                "activo": False if a.interno else base.get("activo", True),
            }
        )

    ids: dict[str, str] = {}
    for inicio in range(0, len(filas), 200):
        guardados = (await db.table("catalogo_items").upsert(filas[inicio : inicio + 200], on_conflict="codigo").execute()).data or []
        ids.update({f["codigo"]: f["id"] for f in guardados})

    precios = [
        {"item_id": ids[a.codigo], "lista_id": lista["id"], "precio": float(a.precio)}
        for a in cargables
        if a.precio is not None and a.codigo in ids
    ]
    for inicio in range(0, len(precios), 200):
        await db.table("precios_items").upsert(precios[inicio : inicio + 200], on_conflict="item_id,lista_id").execute()

    creados = sum(1 for c in codigos if c not in existentes)
    print(f"Catálogo: {creados} creados, {len(codigos) - creados} actualizados, {len(precios)} precios en '{lista['nombre']}'.")

    if desactivar_ejemplo:
        de_ejemplo = (await db.table("catalogo_items").select("id, codigo").or_("codigo.like.*-0*,codigo.like.PRUEBA-*").execute()).data or []
        ejemplo = [f for f in de_ejemplo if re.match(r"^(SIL|MES|LOU|BAR|ILU|MAN|DEC|TAR|CAR)-0\d\d$|^PRUEBA-", f["codigo"])]
        for inicio in range(0, len(ejemplo), 100):
            await db.table("catalogo_items").update({"activo": False}).in_("id", [f["id"] for f in ejemplo[inicio : inicio + 100]]).execute()
        print(f"Catálogo de ejemplo desactivado: {len(ejemplo)} ítems ({', '.join(sorted(f['codigo'] for f in ejemplo))}).")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--aplicar", action="store_true", help="Escribe en Supabase (sin esto sólo muestra la vista previa)")
    parser.add_argument("--lista", default="Público", help="Lista de precios para la columna PRECIO")
    parser.add_argument("--sin-codigo", choices=["provisional", "omitir"], default="provisional")
    parser.add_argument("--desactivar-ejemplo", action="store_true", help="Desactiva el catálogo de ejemplo (SIL-001…) y los PRUEBA-*")
    parser.add_argument("--csv", type=Path, default=RAIZ_BACKEND / "salidas" / "inventario_vista_previa.csv")
    args = parser.parse_args()

    import json

    mapeo = json.loads((RAIZ_BACKEND / "fixtures" / "mapeo_columnas.json").read_text(encoding="utf-8"))
    patron = (mapeo.get("pdf") or {}).get("codigo_en_descripcion") or REGEX_CODIGO_POR_DEFECTO

    articulos, descartados = leer_inventario(args.pdf)
    articulos = normalizar(articulos, patron, args.sin_codigo)
    reporte(articulos, descartados, args.csv)
    if args.aplicar:
        asyncio.run(aplicar(articulos, args.lista, args.desactivar_ejemplo))
    else:
        print("\nVista previa: no se escribió nada. Agrega --aplicar para cargar.")


if __name__ == "__main__":
    main()
