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


_FILAS_PDF = """
  <tr><th>Código</th><th>Descripción</th><th>Cantidad</th><th>Precio</th></tr>
  <tr><td>SIL-001</td><td>Silla Tiffany blanca</td><td>10</td><td>45.00</td></tr>
  <tr><td>MES-002</td><td>Mesa redonda 1.80 m</td><td>4</td><td>250.00</td></tr>
  <tr><td></td><td>Letrero a medida</td><td>1</td><td>2200.00</td></tr>
"""


def _pdf_desde_html(estilo_tabla: str) -> bytes:
    from tests.conftest import requerir_weasyprint

    weasyprint = requerir_weasyprint()
    html = f"""
    <html><head><style>
      body {{ font-family: sans-serif; font-size: 11pt; }}
      table {{ border-collapse: collapse; width: 100%; }}
      td, th {{ padding: 4pt 8pt; text-align: left; {estilo_tabla} }}
    </style></head><body>
      <p>Cliente: Cliente PDF</p><p>Referencia: COT-PDF-1</p>
      <table>{_FILAS_PDF}</table>
    </body></html>
    """
    return weasyprint.HTML(string=html).write_pdf()


def _verificar_pdf(leido, estrategia_esperada: str) -> None:
    assert leido.nombre_cliente == "Cliente PDF"
    assert leido.referencia_externa == "COT-PDF-1"
    assert [f.codigo for f in leido.filas] == ["SIL-001", "MES-002", ""]
    assert leido.filas[2].precio_unitario == Decimal("2200.00")
    assert leido.filas[1].cantidad == Decimal("4")
    assert any(f"estrategia '{estrategia_esperada}'" in a for a in leido.advertencias)


def test_pdf_con_tabla(mapeo):
    """PDF con bordes reales (CSS): lo detecta la estrategia de líneas de pdfplumber."""
    pdf = _pdf_desde_html("border: 1px solid #000;")
    _verificar_pdf(leer_export(pdf, "export.pdf", mapeo), "lineas")


def test_pdf_sin_bordes_usa_estrategia_de_texto(mapeo):
    """PDF sin bordes (sólo texto alineado): la estrategia de líneas no encuentra nada y cae a texto."""
    pdf = _pdf_desde_html("border: none;")
    _verificar_pdf(leer_export(pdf, "export.pdf", mapeo), "texto")


def test_pdf_estrategia_forzada_desde_el_mapeo(mapeo):
    pdf = _pdf_desde_html("border: none;")
    forzado = {**mapeo, "pdf": {"estrategia": "texto"}}
    _verificar_pdf(leer_export(pdf, "export.pdf", forzado), "texto")
    with pytest.raises(ErrorParser, match="desconocida"):
        leer_export(pdf, "export.pdf", {**mapeo, "pdf": {"estrategia": "magia"}})


# ---------------------------------------------------------------------------
# Formato PDF del sistema de la empresa (estrategia "renglones")
# ---------------------------------------------------------------------------

FIXTURE_PDF = RAIZ / "fixtures" / "export_ejemplo.pdf"


@pytest.fixture(scope="module")
def export_pdf_sistema(mapeo):
    assert FIXTURE_PDF.exists(), "Falta fixtures/export_ejemplo.pdf; corre scripts/generar_export_pdf_ejemplo.py"
    return leer_export(FIXTURE_PDF.read_bytes(), FIXTURE_PDF.name, mapeo)


def test_pdf_sistema_metadatos(export_pdf_sistema):
    assert export_pdf_sistema.nombre_cliente == "HACIENDA SAN PEDRO EVENTOS"
    assert export_pdf_sistema.referencia_externa == "12345"
    assert export_pdf_sistema.advertencias == ["PDF leído con la estrategia 'renglones'."]


def test_pdf_sistema_partidas_codigos_y_secciones(export_pdf_sistema):
    from scripts.generar_export_pdf_ejemplo import SECCIONES

    esperadas = [(seccion, articulo) for seccion, partidas in SECCIONES for _, articulo, _, _ in partidas]
    assert len(export_pdf_sistema.filas) == len(esperadas) == 12
    codigos = [f.codigo for f in export_pdf_sistema.filas]
    assert codigos[:3] == ["SIL-001", "SIL-004", "MES-002"]
    assert "XXX-999" in codigos and "" in codigos  # inexistente y sin código se conservan
    assert [f.categoria for f in export_pdf_sistema.filas][:3] == ["SILLAS", "SILLAS", "MESA BANQUETE"]


def test_pdf_sistema_descripcion_de_varias_lineas_y_medidas(export_pdf_sistema):
    silla, _, mesa = export_pdf_sistema.filas[:3]
    assert silla.descripcion == "SILLA TIFFANY BLANCA CON COJÍN DE LINO CRUDO (INCLUYE MOÑO)"
    # "1.80" es una medida, no un monto: debe quedarse en la descripción.
    assert mesa.descripcion == "MESA REDONDA DE 1.80 DIAMETRO (FORRADA EN BLANCO CON BASE BLANCA)"


def test_pdf_sistema_montos_y_reposicion(export_pdf_sistema):
    from scripts.generar_export_pdf_ejemplo import total_esperado

    primera = export_pdf_sistema.filas[0]
    assert (primera.cantidad, primera.precio_unitario, primera.importe) == (Decimal("120"), Decimal("45.00"), Decimal("5400.00"))
    assert primera.costo_reposicion == Decimal("900.00")
    assert export_pdf_sistema.filas[4].precio_unitario == Decimal("1800.00")  # "$1,800.00"
    assert sum(f.importe for f in export_pdf_sistema.filas) == total_esperado()


def test_generador_pdf_reproduce_el_fixture(tmp_path, mapeo):
    from tests.conftest import requerir_weasyprint

    requerir_weasyprint()
    from scripts.generar_export_pdf_ejemplo import generar

    ruta = generar(tmp_path / "export.pdf")
    leido = leer_export(ruta.read_bytes(), ruta.name, mapeo)
    original = leer_export(FIXTURE_PDF.read_bytes(), FIXTURE_PDF.name, mapeo)
    assert [(f.codigo, f.descripcion, f.importe) for f in leido.filas] == [(f.codigo, f.descripcion, f.importe) for f in original.filas]


def test_estrategia_renglones_forzada_falla_con_pdf_de_tabla(mapeo):
    pdf = _pdf_desde_html("border: 1px solid #000;")
    with pytest.raises(ErrorParser, match="renglones"):
        leer_export(pdf, "export.pdf", {**mapeo, "pdf": {**mapeo["pdf"], "estrategia": "renglones"}})


@pytest.mark.parametrize(
    "articulo, codigo, resto",
    [
        ("1040 - MESA REDONDA DE PAROTA 1.80", "1040", "MESA REDONDA DE PAROTA 1.80"),
        ("10081- MESA REDONDA ENCINO 1.80(NUEVAS)", "10081", "MESA REDONDA ENCINO 1.80(NUEVAS)"),
        ("OC2050 - FUNDA BLANCA SNOW SILLA IMPERIAL", "OC2050", "FUNDA BLANCA SNOW SILLA IMPERIAL"),
        ("SIL-001 - SILLA TIFFANY", "SIL-001", "SILLA TIFFANY"),
        ("FUNDA IMPERIAL BLANCA GINEBRA", "", "FUNDA IMPERIAL BLANCA GINEBRA"),
        ("MESA BASE 2.44 X 1.22 - MAMPARA", "", "MESA BASE 2.44 X 1.22 - MAMPARA"),
    ],
)
def test_codigo_dentro_del_articulo(mapeo, articulo, codigo, resto):
    from app.servicios.parser_export import _separar_codigo

    assert _separar_codigo(articulo, mapeo["pdf"]["codigo_en_descripcion"]) == (codigo, resto)
