from decimal import Decimal
from pathlib import Path

import pytest

from app.servicios.parser_export import (
    ErrorParser,
    a_decimal,
    cargar_mapeo,
    leer_export,
    normalizar_texto,
)
from scripts.generar_export_ejemplo import FILAS, generar

RAIZ = Path(__file__).resolve().parent.parent
FIXTURE = RAIZ / "fixtures" / "export_ejemplo.xlsx"


@pytest.fixture(scope="module")
def mapeo():
    return cargar_mapeo(RAIZ / "fixtures" / "mapeo_columnas.json")


@pytest.fixture(scope="module")
def export_fixture(mapeo):
    assert FIXTURE.exists(), "Falta fixtures/export_ejemplo.xlsx; corre scripts/generar_export_ejemplo.py"
    return leer_export(FIXTURE.read_bytes(), FIXTURE.name, mapeo)


def test_metadatos_desde_celdas(export_fixture):
    assert export_fixture.nombre_cliente == "Hacienda San Pedro Eventos"
    assert export_fixture.referencia_externa == "COT-2026-0142"


def test_lee_todas_las_filas_y_omite_total(export_fixture):
    assert len(export_fixture.filas) == len(FILAS) == 12
    assert any("Total" in a for a in export_fixture.advertencias)
    assert [f.orden for f in export_fixture.filas] == list(range(12))


def test_conserva_item_sin_codigo_y_codigo_inexistente(export_fixture):
    sin_codigo = [f for f in export_fixture.filas if not f.codigo]
    assert len(sin_codigo) == 1
    assert sin_codigo[0].descripcion.startswith("Letrero personalizado")
    assert any(f.codigo == "XXX-999" for f in export_fixture.filas)


def test_cantidades_y_precios_como_decimal(export_fixture):
    primera = export_fixture.filas[0]
    assert primera.codigo == "SIL-001"
    assert primera.cantidad == Decimal("120")
    assert primera.precio_unitario == Decimal("45")
    assert isinstance(primera.precio_unitario, Decimal)


def test_generador_reproduce_el_fixture(tmp_path, mapeo):
    ruta = generar(tmp_path / "export.xlsx")
    leido = leer_export(ruta.read_bytes(), ruta.name, mapeo)
    assert [f.codigo for f in leido.filas] == [c for c, *_ in FILAS]


def test_encabezados_se_comparan_sin_acentos(mapeo, tmp_path):
    from openpyxl import Workbook

    libro = Workbook()
    hoja = libro.active
    hoja["B2"] = "Cliente X"
    hoja["B3"] = "REF-1"
    hoja.append([])
    hoja.append(["CODIGO", "descripcion", "  Cantidad ", "Precio unitario"])
    hoja.append(["abc-1", "Cosa", "2", "$1,250.50"])
    ruta = tmp_path / "e.xlsx"
    libro.save(ruta)

    leido = leer_export(ruta.read_bytes(), "e.xlsx", mapeo)
    assert len(leido.filas) == 1
    assert leido.filas[0].cantidad == Decimal("2")
    assert leido.filas[0].precio_unitario == Decimal("1250.50")


def test_falta_columna_lanza_error_claro(mapeo, tmp_path):
    from openpyxl import Workbook

    libro = Workbook()
    hoja = libro.active
    for _ in range(4):
        hoja.append([])
    hoja.append(["Clave", "Descripción", "Cantidad", "Precio"])
    ruta = tmp_path / "e.xlsx"
    libro.save(ruta)
    with pytest.raises(ErrorParser, match="codigo"):
        leer_export(ruta.read_bytes(), "e.xlsx", mapeo)


def test_formato_no_soportado(mapeo):
    with pytest.raises(ErrorParser, match="Formato no soportado"):
        leer_export(b"hola", "export.csv", mapeo)


@pytest.mark.parametrize(
    "entrada, esperado",
    [
        (None, Decimal("0")),
        ("", Decimal("0")),
        (12, Decimal("12")),
        (12.5, Decimal("12.5")),
        ("$1,234.50", Decimal("1234.50")),
        ("1.234,50", Decimal("1234.50")),
        ("1,50", Decimal("1.50")),
        ("2,000", Decimal("2000")),
        ("MXN 350.00 ", Decimal("350.00")),
    ],
)
def test_a_decimal(entrada, esperado):
    assert a_decimal(entrada) == esperado


def test_normalizar_texto():
    assert normalizar_texto("  Código  ") == "codigo"
    assert normalizar_texto("DESCRIPCIÓN") == "descripcion"


def test_pdf_con_tabla(mapeo):
    """Genera un PDF con WeasyPrint y lo vuelve a leer con pdfplumber (ida y vuelta)."""
    from tests.conftest import requerir_weasyprint

    weasyprint = requerir_weasyprint()
    html = """
    <html><body style="font-family: sans-serif">
      <p>Cliente: Cliente PDF</p><p>Referencia: COT-PDF-1</p>
      <table border="1" style="border-collapse: collapse; width: 100%">
        <tr><th>Código</th><th>Descripción</th><th>Cantidad</th><th>Precio</th></tr>
        <tr><td>SIL-001</td><td>Silla Tiffany blanca</td><td>10</td><td>45.00</td></tr>
        <tr><td></td><td>Letrero a medida</td><td>1</td><td>2200.00</td></tr>
      </table>
    </body></html>
    """
    pdf = weasyprint.HTML(string=html).write_pdf()
    leido = leer_export(pdf, "export.pdf", mapeo)
    assert leido.nombre_cliente == "Cliente PDF"
    assert leido.referencia_externa == "COT-PDF-1"
    assert [f.codigo for f in leido.filas] == ["SIL-001", ""]
    assert leido.filas[1].precio_unitario == Decimal("2200.00")
