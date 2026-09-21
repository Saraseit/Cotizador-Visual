"""Fotos de las partidas del PDF de cotización: extracción, asignación y guardado sin duplicados."""

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from app.servicios.fotos_pdf import LADO_MAXIMO_PX, FotoPartida, extraer_fotos_partidas, guardar_en_biblioteca
from app.servicios.parser_export import cargar_mapeo, leer_export
from scripts.generar_export_pdf_ejemplo import color_de_foto

RAIZ = Path(__file__).resolve().parent.parent
FIXTURE_PDF = RAIZ / "fixtures" / "export_ejemplo.pdf"


@pytest.fixture(scope="module")
def export_y_fotos():
    datos = FIXTURE_PDF.read_bytes()
    export = leer_export(datos, FIXTURE_PDF.name, cargar_mapeo(RAIZ / "fixtures" / "mapeo_columnas.json"))
    return export, extraer_fotos_partidas(datos, export.filas)


def _color(foto: FotoPartida) -> tuple[int, int, int]:
    return Image.open(BytesIO(foto.datos)).convert("RGB").resize((1, 1)).getpixel((0, 0))


# ---------------------------------------------------------------------------
# Extracción
# ---------------------------------------------------------------------------

def test_cada_foto_cae_en_su_partida_aunque_cruce_de_pagina(export_y_fotos):
    export, fotos = export_y_fotos
    assert {f.pagina for f in export.filas} == {0, 1}  # el fixture ocupa dos páginas
    for fila in export.filas:
        if fila.orden not in fotos:
            continue
        esperado = color_de_foto(fila.orden)
        assert all(abs(a - b) <= 4 for a, b in zip(_color(fotos[fila.orden]), esperado)), fila.codigo


def test_partidas_sin_foto_y_logo_ignorado(export_y_fotos):
    export, fotos = export_y_fotos
    sin_foto = {f.codigo or "(sin código)" for f in export.filas if f.orden not in fotos}
    assert sin_foto == {"TAR-001", "(sin código)"}
    assert len(fotos) == 10  # 12 partidas menos 2 sin foto; el logo del encabezado no se asigna


def test_fotos_normalizadas_a_jpeg_y_huella_estable(export_y_fotos):
    export, fotos = export_y_fotos
    for foto in fotos.values():
        imagen = Image.open(BytesIO(foto.datos))
        assert imagen.format == "JPEG" and max(imagen.size) <= LADO_MAXIMO_PX
    otra_vez = extraer_fotos_partidas(FIXTURE_PDF.read_bytes(), export.filas)
    assert {o: f.huella for o, f in fotos.items()} == {o: f.huella for o, f in otra_vez.items()}
    assert len({f.huella for f in fotos.values()}) == len(fotos)  # colores distintos, huellas distintas


def test_sin_posiciones_no_hay_fotos(export_y_fotos):
    export, _ = export_y_fotos
    sin_posicion = [SimpleNamespace(orden=f.orden, pagina=None, top=None) for f in export.filas]
    assert extraer_fotos_partidas(FIXTURE_PDF.read_bytes(), sin_posicion) == {}
    assert extraer_fotos_partidas(b"no es un pdf", export.filas) == {}


# ---------------------------------------------------------------------------
# Guardado en la biblioteca (base y Storage simulados)
# ---------------------------------------------------------------------------

class _Consulta:
    def __init__(self, base: "BaseFalsa"):
        self.base, self.filtro, self.fila = base, None, None

    def select(self, *_):
        return self

    def in_(self, columna, valores):
        self.filtro = (columna, set(valores))
        return self

    def insert(self, fila):
        self.fila = dict(fila)
        return self

    async def execute(self):
        if self.fila is not None:
            if self.fila["tipo"] == "oficial" and any(
                i["item_id"] == self.fila["item_id"] and i["tipo"] == "oficial" for i in self.base.imagenes
            ):
                raise RuntimeError("duplicate key value violates unique constraint imagenes_oficial_unica_idx")
            nueva = {**self.fila, "id": f"img-{len(self.base.imagenes) + 1}"}
            self.base.imagenes.append(nueva)
            return SimpleNamespace(data=[nueva])
        columna, valores = self.filtro
        assert columna == "origen->>huella"
        return SimpleNamespace(data=[i for i in self.base.imagenes if (i.get("origen") or {}).get("huella") in valores])


class BaseFalsa:
    def __init__(self, imagenes=None):
        self.imagenes = list(imagenes or [])

    def table(self, nombre):
        assert nombre == "imagenes"
        return _Consulta(self)


class StorageFalso:
    bucket_imagenes = "imagenes"

    def __init__(self):
        self.subidas: dict[str, bytes] = {}

    async def subir(self, bucket, ruta, datos, content_type, sobrescribir=False):
        self.subidas[ruta] = datos
        return ruta


def _foto(orden: int, huella: str) -> FotoPartida:
    return FotoPartida(orden, b"\xff\xd8jpeg", huella, 10, 10)


def _escenario():
    filas = [SimpleNamespace(orden=i) for i in range(3)]
    resultados = [
        SimpleNamespace(item_id="item-a", tipo_item="catalogo"),  # sin oficial todavía
        SimpleNamespace(item_id="item-b", tipo_item="catalogo"),  # ya tiene oficial
        SimpleNamespace(item_id=None, tipo_item="ad_hoc"),  # fuera de catálogo
    ]
    catalogo = {"A-1": {"id": "item-a", "codigo": "A-1"}, "B-2": {"id": "item-b", "codigo": "B-2"}}
    oficial_b = {"id": "img-b", "item_id": "item-b", "tipo": "oficial", "origen": {}}
    fotos = {0: _foto(0, "h-a"), 1: _foto(1, "h-b"), 2: _foto(2, "h-c")}
    return filas, resultados, catalogo, oficial_b, fotos


async def test_guarda_oficial_variante_y_suelta_y_no_duplica():
    filas, resultados, catalogo, oficial_b, fotos = _escenario()
    base, storage = BaseFalsa([oficial_b]), StorageFalso()
    por_item = {"item-b": [oficial_b]}

    nuevas, por_orden = await guardar_en_biblioteca(base, storage, filas, resultados, catalogo, por_item, fotos, "u-1", "12479")
    assert nuevas == 3
    guardadas = {i["origen"].get("huella"): i for i in base.imagenes if i["origen"]}
    assert guardadas["h-a"]["tipo"] == "oficial" and guardadas["h-a"]["item_id"] == "item-a"
    assert guardadas["h-b"]["tipo"] == "variante" and guardadas["h-b"]["item_id"] == "item-b"
    assert guardadas["h-c"]["item_id"] is None
    assert guardadas["h-a"]["origen"] == {"fuente": "pdf_cotizacion", "referencia": "12479", "huella": "h-a"}
    assert any(r.startswith("catalogo/A-1/") for r in storage.subidas) and any(r.startswith("ad_hoc/cotizaciones/") for r in storage.subidas)
    assert [i["id"] for i in por_item["item-a"]] == [guardadas["h-a"]["id"]]  # el matching la verá como oficial
    assert set(por_orden) == {0, 1, 2}

    # Segunda subida de la misma cotización: nada nuevo, mismas imágenes.
    storage.subidas.clear()
    nuevas2, por_orden2 = await guardar_en_biblioteca(base, storage, filas, resultados, catalogo, {}, fotos, "u-1", "12479")
    assert nuevas2 == 0 and por_orden2 == por_orden and storage.subidas == {}


async def test_misma_foto_en_otro_articulo_si_se_guarda():
    filas, resultados, catalogo, _, fotos = _escenario()
    base = BaseFalsa([{"id": "img-x", "item_id": "item-z", "tipo": "oficial", "origen": {"huella": "h-a"}}])
    nuevas, _ = await guardar_en_biblioteca(base, StorageFalso(), filas[:1], resultados[:1], catalogo, {}, {0: fotos[0]}, None, "1")
    assert nuevas == 1  # la huella existe, pero en otro artículo


async def test_oficial_concurrente_se_guarda_como_variante():
    filas, resultados, catalogo, _, fotos = _escenario()
    # La base ya tiene oficial de item-a pero el llamador no lo sabía (otra subida simultánea).
    base = BaseFalsa([{"id": "img-previa", "item_id": "item-a", "tipo": "oficial", "origen": {}}])
    nuevas, _ = await guardar_en_biblioteca(base, StorageFalso(), filas[:1], resultados[:1], catalogo, {}, {0: fotos[0]}, None, "1")
    assert nuevas == 1
    assert base.imagenes[-1]["tipo"] == "variante"
