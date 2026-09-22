"""Flete y montaje como cargos, totales con IVA del documento y secciones en la propuesta."""

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from app.db.modelos import CotizacionDetalle, CotizacionItem
from app.routers.cotizaciones import calcular_totales
from app.servicios.cargos import clasificar_cargo
from app.servicios.parser_export import cargar_mapeo, leer_export
from app.servicios.render_pdf import construir_contexto, renderizar_html

RAIZ = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize(
    "descripcion, categoria, esperado",
    [
        ("FLETE IDA Y REGRESO", "", "flete"),
        ("Flete Mérida - Tulum", "", "flete"),
        ("TRANSPORTE DE MOBILIARIO", "", "flete"),
        ("TRASLADO A HACIENDA", "", "flete"),
        ("MONTAJE Y DESMONTAJE", "", "montaje"),
        ("SERVICIO DE INSTALACIÓN", "", "montaje"),
        ("DESMONTAJE", "", "montaje"),
        ("FLETE Y MONTAJE", "", "flete"),  # gana la primera palabra
        ("MONTAJE Y FLETE", "", "montaje"),
        ("COORDINACIÓN", "MONTAJE", "montaje"),  # sección MONTAJE del sistema
        # Casos reales del inventario que NO son cargos:
        ("TEEPEE CUADRADO RUSTICO ( SIN INSTALACION ELECTRICA )", "ARTICULOS DECORATIVOS", None),
        ("MESA PERIQUERA GRAPA LARGA LIENZO 2.4 METROS (NO INCLUYE MONTAJE)", "MESA PERIQUERA", None),
        ("SILLA IMPERIAL ENFUNDABLE", "SILLAS", None),
        ("LAMPARA BIRD´S NEST CON ILUMINACION", "OTRO CIELO", None),
        ("PORTAFLETES", "", None),  # sólo palabra completa
    ],
)
def test_clasificar_cargo(descripcion, categoria, esperado):
    assert clasificar_cargo(descripcion, categoria) == esperado


def _item(orden, descripcion, importe, categoria="", cargo=None, estado="sugerida"):
    return CotizacionItem(
        id=uuid4(), cotizacion_id=uuid4(), descripcion_origen=descripcion, cantidad=1, precio_unitario=importe,
        importe=importe, tipo_item="catalogo", orden=orden, categoria=categoria, cargo=cargo, estado=estado,
    )


def _items():
    return [
        _item(0, "SILLA TIFFANY", 1000, "SILLAS"),
        _item(1, "SILLA CROSSBACK", 500, "SILLAS", estado="falta_imagen"),
        _item(2, "MESA REDONDA", 2000, "MESA BANQUETE"),
        _item(3, "FLETE IDA", 300, cargo="flete", estado="falta_imagen"),
        _item(4, "FLETE REGRESO", 200, cargo="flete", estado="falta_imagen"),
        _item(5, "MONTAJE", 400, cargo="montaje", estado="falta_imagen"),
    ]


def test_totales_con_iva_del_documento():
    t = calcular_totales(_items(), Decimal("704.00"))
    assert (t["subtotal"], t["flete"], t["montaje"], t["iva"]) == (3500, 500, 400, 704)
    assert t["total"] == 5104
    assert t["total_items"] == 3  # los cargos no son partidas
    assert t["items_pendientes"] == 1  # ni cuentan como "falta imagen"


def test_totales_sin_iva_es_mas_iva():
    t = calcular_totales(_items(), None)
    assert t["iva"] is None and t["total"] == 4400


def _detalle(items, iva):
    ahora = datetime.now(timezone.utc)
    return CotizacionDetalle(
        id=uuid4(), nombre_cliente="Cliente", referencia_externa="R-1", creado_por=uuid4(), creado_en=ahora,
        actualizado_en=ahora, items=items, **calcular_totales(items, iva),
    )


def test_propuesta_agrupa_por_seccion_y_muestra_cargos_abajo():
    contexto = construir_contexto(_detalle(_items(), Decimal("704.00")), {})
    assert [(s.titulo, [i.descripcion for i in s.items]) for s in contexto["secciones"]] == [
        ("SILLAS", ["SILLA TIFFANY", "SILLA CROSSBACK"]),
        ("MESA BANQUETE", ["MESA REDONDA"]),
    ]
    assert contexto["totales"] == [("Subtotal", "$3,500.00"), ("Flete", "$500.00"), ("Montaje", "$400.00"), ("IVA", "$704.00")]
    html = renderizar_html(contexto)
    assert "FLETE IDA" not in html and "FLETE REGRESO" not in html  # no se imprimen como renglón
    assert html.index("SILLAS") < html.index("SILLA TIFFANY") < html.index("MESA BANQUETE") < html.index("MESA REDONDA")
    assert "$5,104.00" in html and "(más IVA)" not in html


def test_propuesta_sin_cargos_ni_iva():
    items = [i for i in _items() if not i.cargo]
    contexto = construir_contexto(_detalle(items, None), {})
    assert contexto["totales"] == [("Subtotal", "$3,500.00")]  # sin renglones de Flete/Montaje/IVA
    assert "(más IVA)" in renderizar_html(contexto)


def test_orden_elegido_manda_sobre_la_seccion():
    # Si el vendedor intercala secciones, se respetan los bloques consecutivos (no se reagrupa solo).
    items = [_item(0, "A", 1, "SILLAS"), _item(1, "B", 1, "MESAS"), _item(2, "C", 1, "SILLAS")]
    contexto = construir_contexto(_detalle(items, None), {})
    assert [s.titulo for s in contexto["secciones"]] == ["SILLAS", "MESAS", "SILLAS"]


def test_pdf_con_flete_montaje_e_iva(tmp_path):
    from tests.conftest import requerir_weasyprint

    requerir_weasyprint()
    from scripts.generar_export_pdf_ejemplo import generar

    secciones = [
        ("SILLAS", [(10, "SIL-001 - SILLA TIFFANY BLANCA", "45.00", "900.00")]),
        ("MONTAJE", [(1, "31 - COORDINACIÓN", "1,500.00", "0.00")]),
        ("SERVICIOS", [(1, "FLETE IDA Y REGRESO", "2,000.00", "0.00")]),
    ]
    ruta = generar(tmp_path / "con_cargos.pdf", secciones, Decimal("632.00"))
    export = leer_export(ruta.read_bytes(), ruta.name, cargar_mapeo(RAIZ / "fixtures" / "mapeo_columnas.json"))
    assert export.iva == Decimal("632.00")
    cargos = [clasificar_cargo(f.descripcion, f.categoria) for f in export.filas]
    assert cargos == [None, "montaje", "flete"]


def test_iva_se_lee_del_pdf_real_de_ejemplo_sin_iva():
    export = leer_export((RAIZ / "fixtures" / "export_ejemplo.pdf").read_bytes(), "e.pdf", cargar_mapeo(RAIZ / "fixtures" / "mapeo_columnas.json"))
    assert export.iva is None  # el fixture sólo trae SubTotal ("más IVA")
