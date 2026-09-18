"""Pruebas de las reglas de los importadores de inventario (sin PDF ni base de datos)."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from scripts.importar_inventario import CODIGOS_INTERNOS, Articulo, normalizar
from scripts.importar_medidas import _formato_mesa, _formato_silla, _separar_diferencia

RAIZ = Path(__file__).resolve().parent.parent
PATRON = json.loads((RAIZ / "fixtures" / "mapeo_columnas.json").read_text(encoding="utf-8"))["pdf"]["codigo_en_descripcion"]


def _articulo(descripcion: str, codigo_columna: str = "", repo: str = "100.00", precio: str = "50.00") -> Articulo:
    return Articulo(
        pagina=1, seccion="SILLAS", codigo_columna=codigo_columna, descripcion=descripcion, existencia="1",
        reposicion=Decimal(repo), precio=Decimal(precio),
    )


def _uno(**kwargs) -> Articulo:
    return normalizar([_articulo(**kwargs)], PATRON, "provisional")[0]


def test_codigo_de_la_descripcion_manda_sobre_la_columna():
    a = _uno(descripcion="2069 - SILLA WASHINGTON RESPALDO OVAL", codigo_columna="20691")
    assert (a.codigo, a.nombre) == ("2069", "SILLA WASHINGTON RESPALDO OVAL")
    assert any("20691" in aviso for aviso in a.avisos)


def test_codigo_solo_en_la_descripcion_o_solo_en_la_columna():
    assert _uno(descripcion="2073- SILLA REBE").codigo == "2073"
    columna = _uno(descripcion="6062 PUFF COLOR ARENA", codigo_columna="6062")
    assert (columna.codigo, columna.nombre) == ("6062", "PUFF COLOR ARENA")
    assert _uno(descripcion="2008.5 - SILLA THONET NEGRA", codigo_columna="2008.5").codigo == "2008.5"


def test_oc_con_espacio_o_guion_suelto():
    a = _uno(descripcion="OC- 2510 MANTEL RECTANGULAR TESSA VAINILLA")
    assert (a.codigo, a.nombre) == ("OC2510", "MANTEL RECTANGULAR TESSA VAINILLA")


def test_sin_codigo_recibe_provisional_estable():
    a = _uno(descripcion="FUNDA IMPERIAL BLANCA GINEBRA")
    b = _uno(descripcion="FUNDA IMPERIAL BLANCA GINEBRA")
    assert a.provisional and a.codigo.startswith("SC-") and a.codigo == b.codigo
    omitido = normalizar([_articulo("ESPEJO AXXIS")], PATRON, "omitir")[0]
    assert omitido.codigo == ""


def test_marcadores_y_reposicion_en_cero_quedan_sin_dato():
    marcador = _uno(descripcion="OC3438 - COPA VINO VERDE", repo="1.00", precio="1.00")
    assert marcador.reposicion is None and marcador.precio is None
    cero = _uno(descripcion="OC2030 - FUNDA ARENA CORTA", repo="0.00", precio="0.00")
    assert cero.reposicion is None and cero.precio == Decimal("0.00")  # precio $0 es real (va incluido)


def test_codigos_repetidos_y_conceptos_internos():
    articulos = normalizar(
        [_articulo("1040 - MESA REDONDA"), _articulo("1040 - OTRA MESA"), _articulo("80 - VIÁTICOS")], PATRON, "provisional"
    )
    assert [a.codigo for a in articulos] == ["1040", "", "80"]
    assert "80" in CODIGOS_INTERNOS and articulos[2].interno


@pytest.mark.parametrize(
    "fisico, existencia, token, esperado",
    [(4, 7, "-395cm", "95cm"), (4, 22, "-1880cm", "80cm"), (4, 4, "070cm", "70cm"), (6, 6, "00cm", "0cm"), (16, 16, "20cm", None)],
)
def test_separar_diferencia_pegada(fisico, existencia, token, esperado):
    assert _separar_diferencia(fisico, existencia, token) == esperado


def test_formatos_de_medidas():
    assert _formato_mesa(["119cm", "240cm", "70cm"]) == "ancho 119 cm · largo 240 cm · alto 70 cm"
    assert _formato_mesa(["0", "0", "55"]) == "alto 55 cm"
    assert _formato_mesa(["0cm", "0cm0", "100cm"]) is None
    assert _formato_silla(["42cm", "112cm", "50ax45l"]) == "respaldo 42 cm · base respaldo 112 cm · asiento 50 × 45 cm"
    assert _formato_silla(["0cm", "80cm", "30AX30L"]) == "base respaldo 80 cm · asiento 30 × 30 cm"
