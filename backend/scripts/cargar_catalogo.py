"""Seeding masivo del catálogo y su biblioteca de imágenes.

Uso:
  python scripts/cargar_catalogo.py --csv fixtures/catalogo_ejemplo.csv --imagenes fixtures/imagenes_ejemplo
  python scripts/cargar_catalogo.py --csv fixtures/catalogo_ejemplo.csv --imagenes fixtures/imagenes_ejemplo --crear-placeholders

CSV con columnas: codigo,nombre,categoria (opcionales: descripcion,medidas,etiquetas separadas por |,costo_reposicion).
Carpeta de imágenes con archivos <codigo>.jpg|png|webp (oficial) y <codigo>-1.jpg, <codigo>-2.jpg (variantes).

Idempotente: los ítems se hacen upsert por código y las imágenes se identifican por su ruta en
Storage (catalogo/<codigo>/<archivo>); correrlo dos veces no duplica nada.
Necesita SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY (se leen del .env de la raíz del repo).
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import mimetypes
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

RAIZ_BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_BACKEND))

from app.config import obtener_configuracion  # noqa: E402
from app.db.cliente import crear_cliente  # noqa: E402
from app.servicios.matching import normalizar_codigo  # noqa: E402

EXTENSIONES = {".png", ".jpg", ".jpeg", ".webp"}
PATRON_VARIANTE = re.compile(r"^(?P<codigo>.+)-(?P<variante>\d{1,2})$")
COLUMNAS_CSV = ("codigo", "nombre", "categoria")


@dataclass
class Reporte:
    items_creados: int = 0
    items_actualizados: int = 0
    imagenes_subidas: int = 0
    imagenes_existentes: int = 0
    archivos_no_asociados: list[str] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)

    def imprimir(self) -> None:
        print("\n===== Resumen del seeding =====")
        print(f"Ítems creados:          {self.items_creados}")
        print(f"Ítems actualizados:     {self.items_actualizados}")
        print(f"Imágenes subidas:       {self.imagenes_subidas}")
        print(f"Imágenes ya existentes: {self.imagenes_existentes}")
        if self.archivos_no_asociados:
            print(f"Archivos no asociados ({len(self.archivos_no_asociados)}):")
            for nombre in self.archivos_no_asociados:
                print(f"  - {nombre}")
        for advertencia in self.advertencias:
            print(f"Aviso: {advertencia}")


def leer_csv(ruta: Path) -> list[dict[str, str]]:
    with open(ruta, encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        faltan = [c for c in COLUMNAS_CSV if c not in (lector.fieldnames or [])]
        if faltan:
            raise SystemExit(f"Al CSV le faltan las columnas: {faltan}. Se esperan: {COLUMNAS_CSV}")
        items: dict[str, dict[str, str]] = {}
        for fila in lector:
            codigo = normalizar_codigo(fila.get("codigo"))
            if not codigo:
                continue
            item = {
                "codigo": codigo,
                "nombre": (fila.get("nombre") or "").strip() or codigo,
                "categoria": (fila.get("categoria") or "").strip(),
                "activo": True,
            }
            # Columnas opcionales: descripcion, medidas, etiquetas (separadas por |), costo_reposicion.
            for opcional in ("descripcion", "medidas"):
                if fila.get(opcional):
                    item[opcional] = fila[opcional].strip()
            if fila.get("etiquetas"):
                item["etiquetas"] = sorted({e.strip().lower() for e in fila["etiquetas"].split("|") if e.strip()})
            if fila.get("costo_reposicion"):
                try:
                    item["costo_reposicion"] = float(fila["costo_reposicion"].replace("$", "").replace(",", ""))
                except ValueError:
                    print(f"Aviso: costo_reposicion inválido en {codigo}: {fila['costo_reposicion']!r}")
            items[codigo] = item
    return list(items.values())


def listar_imagenes(carpeta: Path | None, codigos_conocidos: set[str]) -> list[tuple[Path, str | None, int | None]]:
    """Devuelve (ruta, código normalizado o None si no se pudo asociar, número de variante o None).

    Como los códigos pueden contener guiones y números (SIL-001), primero se prueba el nombre
    completo contra el catálogo y sólo después se interpreta un sufijo -N como variante.
    """
    if carpeta is None:
        return []
    if not carpeta.is_dir():
        raise SystemExit(f"La carpeta de imágenes no existe: {carpeta}")
    resultado: list[tuple[Path, str | None, int | None]] = []
    for ruta in sorted(carpeta.iterdir()):
        if not ruta.is_file() or ruta.suffix.lower() not in EXTENSIONES:
            continue
        base = normalizar_codigo(ruta.stem)
        if base in codigos_conocidos:
            resultado.append((ruta, base, None))
            continue
        coincidencia = PATRON_VARIANTE.match(base)
        if coincidencia and coincidencia.group("codigo") in codigos_conocidos:
            resultado.append((ruta, coincidencia.group("codigo"), int(coincidencia.group("variante"))))
            continue
        resultado.append((ruta, None, None))
    return resultado


async def ejecutar(ruta_csv: Path, carpeta: Path | None) -> Reporte:
    reporte = Reporte()
    config = obtener_configuracion()
    db = await crear_cliente(config)
    bucket = db.storage.from_(config.bucket_imagenes)

    # --- Catálogo -----------------------------------------------------------
    items = leer_csv(ruta_csv)
    codigos = [i["codigo"] for i in items]
    existentes = await db.table("catalogo_items").select("codigo").in_("codigo", codigos).execute()
    ya_existian = {normalizar_codigo(f["codigo"]) for f in existentes.data or []}

    guardados = await db.table("catalogo_items").upsert(items, on_conflict="codigo").execute()
    id_por_codigo = {normalizar_codigo(f["codigo"]): f["id"] for f in guardados.data or []}
    reporte.items_creados = sum(1 for c in codigos if c not in ya_existian)
    reporte.items_actualizados = len(codigos) - reporte.items_creados
    print(f"Catálogo: {reporte.items_creados} creados, {reporte.items_actualizados} actualizados.")

    # --- Imágenes -----------------------------------------------------------
    archivos = listar_imagenes(carpeta, set(id_por_codigo))
    if not archivos:
        return reporte

    rutas_storage = {f"catalogo/{codigo}/{ruta.name}" for ruta, codigo, _ in archivos if codigo}
    registradas = await db.table("imagenes").select("ruta_storage, item_id, tipo").in_("ruta_storage", sorted(rutas_storage)).execute()
    rutas_registradas = {f["ruta_storage"] for f in registradas.data or []}

    oficiales = await db.table("imagenes").select("item_id").eq("tipo", "oficial").in_("item_id", list(id_por_codigo.values())).execute()
    items_con_oficial = {f["item_id"] for f in oficiales.data or []}

    for ruta, codigo, variante in archivos:
        item_id = id_por_codigo.get(codigo) if codigo else None
        if item_id is None:
            reporte.archivos_no_asociados.append(ruta.name)
            continue
        ruta_storage = f"catalogo/{codigo}/{ruta.name}"
        if ruta_storage in rutas_registradas:
            reporte.imagenes_existentes += 1
            continue

        tipo = "oficial" if variante is None else "variante"
        if tipo == "oficial" and item_id in items_con_oficial:
            reporte.advertencias.append(f"{ruta.name}: el ítem ya tenía imagen oficial; se guardó como variante.")
            tipo = "variante"

        content_type = mimetypes.guess_type(ruta.name)[0] or "application/octet-stream"
        await bucket.upload(ruta_storage, ruta.read_bytes(), {"content-type": content_type, "upsert": "true"})
        await db.table("imagenes").insert(
            {
                "item_id": item_id,
                "ruta_storage": ruta_storage,
                "tipo": tipo,
                "etiquetas": ["seed"],
                "origen": {"nombre_archivo": ruta.name, "origen": "cargar_catalogo"},
            }
        ).execute()
        if tipo == "oficial":
            items_con_oficial.add(item_id)
        reporte.imagenes_subidas += 1
        print(f"  subida {ruta_storage} ({tipo})")

    return reporte


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--csv", required=True, type=Path, help="CSV con codigo,nombre,categoria")
    parser.add_argument("--imagenes", type=Path, help="Carpeta con <codigo>.png|jpg y <codigo>-N.png|jpg")
    parser.add_argument(
        "--crear-placeholders",
        action="store_true",
        help="Genera PNG grises con el código para los ítems sin archivo en la carpeta (desarrollo)",
    )
    args = parser.parse_args()

    if args.crear_placeholders:
        if args.imagenes is None:
            raise SystemExit("--crear-placeholders necesita --imagenes <carpeta destino>")
        from scripts.generar_placeholders import crear_placeholders

        creadas = crear_placeholders(args.csv, args.imagenes, omitir={"TAR-001", "CAR-001"}, con_variante={"SIL-001", "MES-002"})
        print(f"Marcadores de posición creados: {len(creadas)}")

    reporte = asyncio.run(ejecutar(args.csv, args.imagenes))
    reporte.imprimir()


if __name__ == "__main__":
    main()
