from app.servicios.matching import (
    agrupar_imagenes,
    elegir_imagen_sugerida,
    indexar_catalogo,
    normalizar_codigo,
    resolver_filas,
    resolver_item,
)

CATALOGO = indexar_catalogo(
    [
        {"id": "item-silla", "codigo": "SIL-001", "nombre": "Silla"},
        {"id": "item-mesa", "codigo": "mes-002 ", "nombre": "Mesa"},
        {"id": "item-sin-imagen", "codigo": "TAR-001", "nombre": "Tarima"},
    ]
)
IMAGENES = agrupar_imagenes(
    [
        {"id": "img-oficial", "item_id": "item-silla", "tipo": "oficial", "usos": 0},
        {"id": "img-var-popular", "item_id": "item-silla", "tipo": "variante", "usos": 9},
        {"id": "img-var-1", "item_id": "item-mesa", "tipo": "variante", "usos": 2},
        {"id": "img-var-2", "item_id": "item-mesa", "tipo": "variante", "usos": 7},
        {"id": "img-generada", "item_id": "item-mesa", "tipo": "generada", "usos": 50},
        {"id": "img-huerfana", "item_id": None, "tipo": "variante", "usos": 1},
    ]
)


def test_normalizar_codigo():
    assert normalizar_codigo("  sil - 001 ") == "SIL-001"
    assert normalizar_codigo(None) == ""
    assert normalizar_codigo(123) == "123"


def test_match_exacto_prefiere_oficial_sobre_variante_popular():
    r = resolver_item("sil-001", CATALOGO, IMAGENES)
    assert r.tipo_item == "catalogo"
    assert r.item_id == "item-silla"
    assert r.imagen_id == "img-oficial"


def test_sin_oficial_toma_variante_con_mas_usos_ignorando_generadas():
    r = resolver_item("MES-002", CATALOGO, IMAGENES)
    assert r.item_id == "item-mesa"
    assert r.imagen_id == "img-var-2"


def test_match_sin_imagenes_deja_imagen_nula():
    r = resolver_item("TAR-001", CATALOGO, IMAGENES)
    assert r.tipo_item == "catalogo"
    assert r.imagen_id is None


def test_codigo_inexistente_o_vacio_es_ad_hoc():
    for codigo in ("XXX-999", "", None, "   "):
        r = resolver_item(codigo, CATALOGO, IMAGENES)
        assert r.tipo_item == "ad_hoc"
        assert r.item_id is None
        assert r.imagen_id is None


def test_no_hay_matching_difuso_por_nombre():
    # "Silla" es el nombre del ítem, no su código: no debe resolver.
    assert resolver_item("Silla", CATALOGO, IMAGENES).tipo_item == "ad_hoc"


def test_resolver_filas_conserva_orden():
    resultados = resolver_filas(["SIL-001", "", "MES-002"], CATALOGO, IMAGENES)
    assert [r.tipo_item for r in resultados] == ["catalogo", "ad_hoc", "catalogo"]


def test_elegir_imagen_sin_candidatas():
    assert elegir_imagen_sugerida([]) is None
    assert elegir_imagen_sugerida([{"id": "g", "tipo": "generada", "usos": 3}]) is None


def test_agrupar_ignora_huerfanas():
    assert "None" not in IMAGENES
    assert len(IMAGENES["item-mesa"]) == 3
