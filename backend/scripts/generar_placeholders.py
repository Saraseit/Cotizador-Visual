"""Crea imágenes de marcador de posición (PNG gris con el código escrito) para desarrollar sin fotos.

Uso:
  python scripts/generar_placeholders.py --csv fixtures/catalogo_ejemplo.csv --destino fixtures/imagenes_ejemplo

Por defecto se omiten TAR-001 y CAR-001 (para que la pantalla Biblioteca tenga ítems sin imagen)
y se crea una variante extra para SIL-001 y MES-002 (para probar el selector).
"""

import argparse
import csv
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONDO = (233, 230, 223)
TEXTO = (87, 83, 74)
FONDO_VARIANTE = (221, 216, 206)
LADO = 800


_FUENTES_SISTEMA = ("DejaVuSans.ttf", "arial.ttf", "Arial.ttf", "LiberationSans-Regular.ttf", "segoeui.ttf")


def _fuente(tamano: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Fuente con acentos: prueba fuentes del sistema y cae en la de Pillow si no hay ninguna."""
    for nombre in _FUENTES_SISTEMA:
        try:
            return ImageFont.truetype(nombre, tamano)
        except OSError:
            continue
    return ImageFont.load_default(size=tamano)


def crear_placeholder(codigo: str, nombre: str, destino: Path, variante: int | None = None) -> Path:
    imagen = Image.new("RGB", (LADO, LADO), FONDO_VARIANTE if variante else FONDO)
    dibujo = ImageDraw.Draw(imagen)

    # Silueta simple para que no sea sólo un rectángulo plano.
    dibujo.rounded_rectangle((120, 260, 680, 560), radius=28, outline=TEXTO, width=6)
    dibujo.line((160, 560, 160, 660), fill=TEXTO, width=6)
    dibujo.line((640, 560, 640, 660), fill=TEXTO, width=6)

    titulo = codigo if variante is None else f"{codigo} · variante {variante}"
    dibujo.text((LADO / 2, 150), titulo, fill=TEXTO, font=_fuente(60), anchor="mm")
    dibujo.text((LADO / 2, 720), nombre[:40], fill=TEXTO, font=_fuente(30), anchor="mm")
    dibujo.text((LADO / 2, 770), "marcador de posición", fill=TEXTO, font=_fuente(20), anchor="mm")

    sufijo = f"-{variante}" if variante else ""
    ruta = destino / f"{codigo}{sufijo}.png"
    imagen.save(ruta, format="PNG", optimize=True)
    return ruta


def crear_placeholders(
    ruta_csv: Path, destino: Path, omitir: set[str], con_variante: set[str], sobrescribir: bool = False
) -> list[Path]:
    destino.mkdir(parents=True, exist_ok=True)
    creadas: list[Path] = []
    with open(ruta_csv, encoding="utf-8-sig", newline="") as archivo:
        for fila in csv.DictReader(archivo):
            codigo = (fila.get("codigo") or "").strip().upper()
            if not codigo or codigo in omitir:
                continue
            nombre = (fila.get("nombre") or "").strip()
            existentes = list(destino.glob(f"{codigo}.*"))
            if not existentes or sobrescribir:
                creadas.append(crear_placeholder(codigo, nombre, destino))
            if codigo in con_variante and (sobrescribir or not list(destino.glob(f"{codigo}-1.*"))):
                creadas.append(crear_placeholder(codigo, nombre, destino, variante=1))
    return creadas


def _lista(texto: str) -> set[str]:
    return {t.strip().upper() for t in texto.split(",") if t.strip()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--destino", required=True, type=Path)
    parser.add_argument("--omitir", default="TAR-001,CAR-001", help="Códigos sin imagen, separados por coma")
    parser.add_argument("--variantes", default="SIL-001,MES-002", help="Códigos que además reciben una variante")
    parser.add_argument("--sobrescribir", action="store_true")
    args = parser.parse_args()

    creadas = crear_placeholders(args.csv, args.destino, _lista(args.omitir), _lista(args.variantes), args.sobrescribir)
    print(f"Marcadores creados: {len(creadas)} en {args.destino}")


if __name__ == "__main__":
    main()
