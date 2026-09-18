"""Llena el campo Medidas del catálogo desde los reportes de inventario físico con dimensiones.

    python scripts/importar_medidas.py "ruta/INVENTARIO SILLAS.pdf" "ruta/INVENTARIO MESAS .pdf" ...           # vista previa
    python scripts/importar_medidas.py ... --aplicar

Formatos que entiende (uno por archivo, se detecta por los encabezados):
  - mesas:           ... EXISTENCIA FISICO DAÑADO TOTAL PZ DIFERENCIA ANCHO LARGO ALTO
  - sillas y bancos: ... EXISTENCIA FISICO DAÑADO TOTAL PZ DIFERENCIA RESPALDO | BASE RESPALDO | ASIENTO

Las medidas se escriben con las etiquetas del reporte ("ancho 119 cm · largo 240 cm · alto 70 cm",
"respaldo 42 cm · base respaldo 112 cm · asiento 50 × 45 cm"); los ceros se omiten.
Sólo se llenan ítems cuyo código exista en el catálogo y cuyo campo Medidas esté vacío (nunca sobrescribe).
En algunos reportes la DIFERENCIA sale pegada a la primera medida ("-395cm" = -3 y 95 cm): se separa
calculando la diferencia como FISICO − EXISTENCIA.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

RAIZ_BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_BACKEND))

from app.servicios.matching import normalizar_codigo  # noqa: E402
from app.servicios.parser_export import REGEX_CODIGO_POR_DEFECTO, _agrupar_renglones, _clave, _separar_codigo, _texto  # noqa: E402

_ENTERO = re.compile(r"^-?\d+$")
_CM = re.compile(r"^(\d+(?:\.\d+)?)(?:cm)?$", re.IGNORECASE)
_ASIENTO = re.compile(r"^(\d+(?:\.\d+)?)a[x×](\d+(?:\.\d+)?)l$", re.IGNORECASE)


@dataclass
class Medida:
    archivo: str
    codigo: str
    descripcion: str
    medidas: str
    crudo: str


def _cm(token: str) -> float | None:
    m = _CM.match(token)
    return float(m.group(1)) if m else None


def _fmt(valor: float) -> str:
    return str(int(valor)) if valor.is_integer() else f"{valor:g}"


def _separar_diferencia(fisico: int, existencia: int, token: str) -> str | None:
    """'-395cm' con diferencia -3 -> '95cm'."""
    diferencia = str(fisico - existencia)
    if token.lower().startswith(diferencia) and _CM.match(token[len(diferencia) :]):
        return token[len(diferencia) :]
    return None


def _formato_mesa(tokens: list[str]) -> str | None:
    etiquetas = ("ancho", "largo", "alto")
    valores = [_cm(t) for t in tokens]
    if any(v is None for v in valores):
        return None
    partes = [f"{e} {_fmt(v)} cm" for e, v in zip(etiquetas, valores) if v]
    return " · ".join(partes)


def _formato_silla(tokens: list[str]) -> str | None:
    respaldo, base, asiento = tokens
    partes: list[str] = []
    for etiqueta, token in (("respaldo", respaldo), ("base respaldo", base)):
        valor = _cm(token)
        if valor is None:
            return None
        if valor:
            partes.append(f"{etiqueta} {_fmt(valor)} cm")
    m = _ASIENTO.match(asiento)
    if m:
        a, l = float(m.group(1)), float(m.group(2))
        if a or l:
            partes.append(f"asiento {_fmt(a)} × {_fmt(l)} cm")
    elif _cm(asiento):
        partes.append(f"asiento {_fmt(_cm(asiento))} cm")
    return " · ".join(partes)


def leer_medidas(ruta: Path, patron_codigo: str) -> tuple[list[Medida], list[str]]:
    import pdfplumber

    medidas: list[Medida] = []
    avisos: list[str] = []
    tipo: str | None = None
    x_numeros = 340.0
    with pdfplumber.open(ruta) as pdf:
        for pagina in pdf.pages:
            renglones = _agrupar_renglones(pagina.extract_words(), tolerancia=2)
            for renglon in renglones:
                claves = _clave(_texto(renglon))
                if "ancho" in claves and "largo" in claves:
                    tipo = "mesa"
                elif "asiento" in claves:
                    tipo = "silla"
                existencia = next((w for w in renglon if _clave(w["text"]).startswith("existenci")), None)
                if existencia is not None:
                    # Las cantidades empiezan bajo EXISTENCIA; las descripciones largas llegan hasta ahí.
                    x_numeros = existencia["x0"] - 15
                    continue
                if tipo is None or len(renglon) < 6 or renglon[0]["x0"] > 60:
                    continue
                # Cantidades y medidas: las palabras de la derecha que no son parte de la descripción.
                derecha = [w["text"] for w in renglon if w["x0"] >= x_numeros]
                enteros = []
                for t in derecha:
                    if _ENTERO.match(t) and len(enteros) < 5:
                        enteros.append(int(t))
                    else:
                        break
                resto = derecha[len(enteros) :]
                if len(enteros) == 4 and len(resto) == 3:
                    # La diferencia viene pegada a la primera medida ("-395cm"); si no se puede separar
                    # y la medida es válida, lo que falta es una cantidad vacía y la medida va tal cual.
                    separada = _separar_diferencia(enteros[1], enteros[0], resto[0])
                    if separada is None and _cm(resto[0]) is None:
                        avisos.append(f"{ruta.name}: no se pudo separar '{resto[0]}' en '{_texto(renglon)[:70]}'")
                        continue
                    resto = [separada or resto[0]] + resto[1:]
                elif len(enteros) != 5 or len(resto) != 3:
                    avisos.append(f"{ruta.name}: renglón no interpretado '{_texto(renglon)[:80]}'")
                    continue

                descripcion = _texto([w for w in renglon[1:] if w["x0"] < x_numeros])
                codigo_desc, resto_desc = _separar_codigo(descripcion, patron_codigo)
                codigo = normalizar_codigo(codigo_desc) or normalizar_codigo(renglon[0]["text"])
                texto = _formato_mesa(resto) if tipo == "mesa" else _formato_silla(resto)
                if texto is None:
                    avisos.append(f"{ruta.name}: medidas no reconocidas {resto} en {codigo}")
                    continue
                if texto:
                    medidas.append(Medida(ruta.name, codigo, resto_desc or descripcion, texto, " ".join(resto)))
    return medidas, avisos


async def aplicar(medidas: list[Medida], solo_vista: bool) -> None:
    from app.config import obtener_configuracion
    from app.db.cliente import crear_cliente

    db = await crear_cliente(obtener_configuracion())
    codigos = sorted({m.codigo for m in medidas})
    catalogo: dict[str, dict] = {}
    for inicio in range(0, len(codigos), 200):
        lote = (await db.table("catalogo_items").select("id, codigo, nombre, medidas").in_("codigo", codigos[inicio : inicio + 200]).execute()).data or []
        catalogo.update({f["codigo"]: f for f in lote})

    por_llenar, ya_tenian, sin_item = [], [], []
    vistos: set[str] = set()
    for m in medidas:
        if m.codigo in vistos:
            continue
        vistos.add(m.codigo)
        item = catalogo.get(m.codigo)
        if item is None:
            sin_item.append(m)
        elif (item.get("medidas") or "").strip():
            ya_tenian.append(m)
        else:
            por_llenar.append((item, m))

    print(f"Medidas leídas: {len(vistos)} códigos | a llenar: {len(por_llenar)} | ya tenían medidas: {len(ya_tenian)} | código no está en el catálogo: {len(sin_item)}")
    for item, m in por_llenar[:12]:
        print(f"  {m.codigo:8} {item['nombre'][:42]:42} -> {m.medidas}")
    if len(por_llenar) > 12:
        print(f"  … y {len(por_llenar) - 12} más")
    for m in sin_item:
        print(f"  no está en el catálogo: {m.codigo} {m.descripcion[:50]} ({m.archivo})")

    if solo_vista:
        print("\nVista previa: no se escribió nada. Agrega --aplicar para guardar.")
        return
    for item, m in por_llenar:
        await db.table("catalogo_items").update({"medidas": m.medidas}).eq("id", item["id"]).execute()
    print(f"\nMedidas guardadas en {len(por_llenar)} ítems.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pdfs", nargs="+", type=Path)
    parser.add_argument("--aplicar", action="store_true")
    args = parser.parse_args()

    mapeo = json.loads((RAIZ_BACKEND / "fixtures" / "mapeo_columnas.json").read_text(encoding="utf-8"))
    patron = (mapeo.get("pdf") or {}).get("codigo_en_descripcion") or REGEX_CODIGO_POR_DEFECTO

    todas: list[Medida] = []
    for ruta in args.pdfs:
        medidas, avisos = leer_medidas(ruta, patron)
        print(f"{ruta.name}: {len(medidas)} con medidas")
        for aviso in avisos:
            print(f"  aviso: {aviso}")
        todas.extend(medidas)
    asyncio.run(aplicar(todas, solo_vista=not args.aplicar))


if __name__ == "__main__":
    main()
