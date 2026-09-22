"""Genera `fixtures/export_ejemplo.pdf`: un export sintético con el mismo formato que el PDF del
sistema de la empresa (sin tabla dibujada, código dentro del artículo, "Reposición" bajo la cantidad,
secciones, "Total de …" por sección y SubTotal al final).

Los datos son ficticios y usan los códigos del catálogo de ejemplo, para que al subirlo en la app se
resuelvan imágenes. Incluye un código inexistente (XXX-999) y un artículo sin código.

Como el PDF real, trae la foto de cada partida en la columna FOTOGRAFÍA (un cuadro de color distinto
por partida, ver `color_de_foto`), salvo en las de `SIN_FOTO`, y el logo en el encabezado.

Uso:  python scripts/generar_export_pdf_ejemplo.py      (necesita WeasyPrint)
"""

from __future__ import annotations

import base64
import sys
from decimal import Decimal
from html import escape
from io import BytesIO
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
DESTINO = RAIZ / "fixtures" / "export_ejemplo.pdf"

CLIENTE = "HACIENDA SAN PEDRO EVENTOS"
SIN_FOTO = {"TAR-001", "LETRERO"}  # partidas sin foto (por código o primera palabra del artículo)
REFERENCIA = "12345"

# sección -> [(cantidad, artículo con código, precio unitario, reposición)]
SECCIONES: list[tuple[str, list[tuple[int, str, str, str]]]] = [
    (
        "SILLAS",
        [
            (120, "SIL-001 - SILLA TIFFANY BLANCA CON COJÍN DE LINO CRUDO (INCLUYE MOÑO)", "45.00", "900.00"),
            (80, "SIL-004 - SILLA CROSSBACK NATURAL", "65.00", "1,300.00"),
        ],
    ),
    (
        "MESA BANQUETE",
        [
            (12, "MES-002 - MESA REDONDA DE 1.80 DIAMETRO (FORRADA EN BLANCO CON BASE BLANCA)", "250.00", "6,000.00"),
            (4, "MES-005 - MESA IMPERIAL MADERA 3 M", "900.00", "9,000.00"),
        ],
    ),
    (
        "LOUNGE Y BARRAS",
        [
            (3, "LOU-001 - SALA LOUNGE LINO CRUDO (3 PIEZAS)", "1,800.00", "15,000.00"),
            (1, "BAR-002 - BARRA DE BEBIDAS MADERA 2.4 M", "3,500.00", "18,000.00"),
        ],
    ),
    (
        "DECORACIÓN",
        [
            (6, "ILU-003 - LÁMPARA DE PIE EDISON", "320.00", "2,500.00"),
            (12, "MAN-001 - MANTEL LINO ARENA 3 M", "120.00", "800.00"),
            (1, "XXX-999 - PÉRGOLA CON CORTINAS DE GASA", "4,500.00", "20,000.00"),
            (1, "LETRERO PERSONALIZADO CON NOMBRE DE LOS NOVIOS", "2,200.00", "2,200.00"),
            (12, "DEC-004 - CENTRO DE MESA FLORAL BAJO", "450.00", "600.00"),
            (1, "TAR-001 - TARIMA 6 X 4 M CON FALDÓN", "5,200.00", "30,000.00"),
        ],
    ),
]


def color_de_foto(indice: int) -> tuple[int, int, int]:
    """Color sólido y distinguible de la foto de la partida `indice` (orden en el export)."""
    return ((indice * 67) % 200 + 40, (indice * 131) % 200 + 40, (indice * 193) % 200 + 40)


def _png(color: tuple[int, int, int], ancho: int = 320, alto: int = 240) -> str:
    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (ancho, alto), color).save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def tiene_foto(articulo: str) -> bool:
    return articulo.split(" ")[0] not in SIN_FOTO


def _pesos(valor: Decimal) -> str:
    return f"${valor:,.2f}"


def _decimal(texto: str) -> Decimal:
    return Decimal(texto.replace(",", ""))


def construir_html(secciones=None, iva: Decimal | None = None) -> str:
    secciones = SECCIONES if secciones is None else secciones
    renglones: list[str] = []
    subtotal = Decimal("0")
    indice = 0
    for seccion, partidas in secciones:
        renglones.append(f'<tr><td></td><td class="seccion">{escape(seccion)}</td><td colspan="3"></td></tr>')
        total_seccion = Decimal("0")
        for cantidad, articulo, precio, reposicion in partidas:
            importe = cantidad * _decimal(precio)
            total_seccion += importe
            foto = f'<img class="foto" src="{_png(color_de_foto(indice))}" alt="">' if tiene_foto(articulo) else ""
            indice += 1
            renglones.append(
                "<tr class=\"partida\">"
                f'<td class="cant">{cantidad}<div class="rep"><b>Reposición</b><br>${reposicion}</div></td>'
                f'<td class="celda-foto">{foto}</td>'
                f'<td class="articulo">{escape(articulo)}</td>'
                f'<td class="monto">${precio}</td>'
                f'<td class="monto">{_pesos(importe)}</td>'
                "</tr>"
            )
        subtotal += total_seccion
        renglones.append(
            f'<tr class="total"><td colspan="3" class="derecha">Total de {escape(seccion)}</td><td></td>'
            f'<td class="monto">{_pesos(total_seccion)}</td></tr>'
        )

    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><style>
  @page {{ size: Letter; margin: 36pt 30pt 60pt 30pt;
          @bottom-left {{ content: "viernes, 18 septiembre, 2026"; font-size: 8pt; }}
          @bottom-right {{ content: "Página " counter(page) " de " counter(pages); font-size: 8pt; }} }}
  body {{ font-family: "DejaVu Sans", sans-serif; font-size: 8pt; }}
  .cabecera {{ display: flex; justify-content: space-between; }}
  .caja {{ border: 1.5pt solid #000; padding: 4pt 12pt; text-align: center; }}
  .caja .numero {{ font-size: 14pt; margin-top: 8pt; }}
  .datos {{ border: 1pt solid #aaa; margin-top: 10pt; padding: 6pt; }}
  .datos span {{ display: inline-block; width: 60pt; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 12pt; }}
  th {{ border: 1pt solid #000; background: #eee; padding: 3pt; }}
  td {{ vertical-align: top; padding: 4pt 3pt 10pt 3pt; }}
  .cant {{ width: 55pt; text-align: right; }}
  .rep {{ text-align: left; margin-top: 14pt; }}
  .articulo {{ width: 190pt; }}
  .monto {{ text-align: right; width: 70pt; }}
  .seccion {{ font-weight: bold; text-align: center; width: 110pt; }}
  .celda-foto {{ width: 110pt; }}
  .foto {{ width: 64pt; height: 48pt; display: block; margin: 0 auto; }}
  .logo {{ width: 60pt; height: 40pt; }}
  .derecha {{ text-align: right; font-weight: bold; }}
</style></head><body>
  <div class="cabecera">
    <div><img class="logo" src="{_png((20, 20, 20), 120, 80)}" alt=""><br>Minimal Estudio SA de CV<br>Mérida, Yucatán</div>
    <div class="caja"><b>Cotización</b><div class="numero">{REFERENCIA}</div></div>
  </div>
  <div class="datos">
    <p><span>Cliente:</span> <b>{escape(CLIENTE)}</b> <span style="margin-left: 120pt">Teléfono:</span> 9990000000</p>
    <p><span>Contacto:</span> CONTACTO DE PRUEBA</p>
  </div>
  <table>
    <thead><tr><th>CANT.</th><th>FOTOGRAFÍA</th><th>ARTÍCULO</th><th>PRECIO UNIT.</th><th>TOTAL</th></tr></thead>
    <tbody>{"".join(renglones)}</tbody>
  </table>
  <p style="margin-top: 16pt">Importe deposito de Garantía: $0.00 &nbsp;&nbsp;&nbsp; SubTotal: {_pesos(subtotal)}</p>
  {f'<p>IVA {_pesos(iva)}</p>' if iva is not None else ''}
  <p>DIAS: 1.0</p>
  <p>Notas: 1.- Todos los precios son mas IVA.</p>
</body></html>"""


def generar(destino: Path = DESTINO, secciones=None, iva: Decimal | None = None) -> Path:
    from app.servicios.render_pdf import _preparar_gtk_en_windows

    _preparar_gtk_en_windows()
    from weasyprint import HTML

    destino.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=construir_html(secciones, iva)).write_pdf(destino)
    return destino


def total_esperado() -> Decimal:
    return sum((c * _decimal(p) for _, partidas in SECCIONES for c, _, p, _ in partidas), Decimal("0"))


if __name__ == "__main__":
    print(f"Generado: {generar()}")
