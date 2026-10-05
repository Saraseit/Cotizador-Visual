"""Edición en Revisar: alineación con el sistema principal, IVA siempre, cuadre y secciones."""

from uuid import uuid4

from app.db.modelos import CotizacionItem
from app.routers.edicion import orden_tras_seccion, seccion_normalizada
from app.servicios import alineacion
from app.servicios import compuestos as servicio


def _item(descripcion, cantidad, precio, orden, categoria="MESAS", origen="sistema", eliminada=False,
          cantidad_nueva=None, precio_nuevo=None, categoria_nueva=None):
    """Partida con lo que dice el sistema (`cantidad`, `precio`, `categoria`) y, si se editó, lo nuevo."""
    actual_cantidad = cantidad if cantidad_nueva is None else cantidad_nueva
    actual_precio = precio if precio_nuevo is None else precio_nuevo
    return CotizacionItem(
        id=uuid4(), cotizacion_id=uuid4(), codigo_origen="COD", descripcion_origen=descripcion, tipo_item="catalogo",
        orden=orden, origen=origen, eliminada=eliminada,
        cantidad=actual_cantidad, precio_unitario=actual_precio, categoria=categoria_nueva or categoria,
        cantidad_sistema=cantidad, precio_sistema=precio, categoria_sistema=categoria,
        importe=round(actual_cantidad * actual_precio, 2),
    )


def _sin_cambios():
    return [(_item("SILLA", 100, 45, 0, "SILLAS")), (_item("MESA", 10, 250, 1))]


def test_sin_cambios_esta_alineada_y_el_iva_es_el_del_documento():
    todas = _sin_cambios()
    assert alineacion.alineacion(todas).alineada
    assert alineacion.base_sistema(todas) == 7000
    totales = servicio.totales(todas, [], 1120, alineacion.base_sistema(todas))
    assert totales["iva"] == 1120 and totales["total"] == 8120


def test_sin_iva_en_el_documento_se_calcula():
    todas = _sin_cambios()
    totales = servicio.totales(todas, [], None, alineacion.base_sistema(todas))
    assert totales["iva"] == 1120  # 16 % de 7,000


def test_cambios_de_cantidad_precio_seccion_agregada_y_quitada():
    silla = (_item("SILLA", 100, 45, 0, "SILLAS", cantidad_nueva=120))
    mesa = (_item("MESA", 10, 250, 1, precio_nuevo=230, categoria_nueva="CEREMONIA"))
    arco = (_item("ARCO DE FLORES", 1, 3000, 2, "CEREMONIA", origen="provista"))
    mantel = (_item("MANTEL", 10, 80, 3, eliminada=True))
    resultado = alineacion.alineacion([silla, mesa, arco, mantel])
    assert not resultado.alineada
    assert [(c.tipo, c.descripcion) for c in resultado.cambios] == [
        ("cantidad", "SILLA"), ("precio", "MESA"), ("seccion", "MESA"), ("agregada", "ARCO DE FLORES"), ("quitada", "MANTEL"),
    ]
    cambio = resultado.cambios[0]
    assert (cambio.antes, cambio.despues) == (100, 120)
    # Sistema: 4,500 + 2,500 + 800 (el mantel quitado sí estaba) = 7,800. Ahora: 5,400 + 2,300 + 3,000 = 10,700.
    assert alineacion.base_sistema([silla, mesa, arco, mantel]) == 7800
    assert resultado.diferencia_importe == 2900


def test_las_ediciones_no_cuentan_como_descuadre():
    silla = (_item("SILLA", 100, 45, 0, "SILLAS", cantidad_nueva=120))
    mesa = (_item("MESA", 10, 250, 1))
    todas = [silla, mesa]
    base = alineacion.base_sistema(todas)  # 7,000
    totales = servicio.totales(todas, [], 1120, base)
    assert totales["subtotal"] == 7900 and totales["iva"] == 1264  # mismo 16 % del documento
    cuadre = servicio.cuadre(todas, [], totales["total"], 7000, 1120, base)
    assert cuadre.diferencia == 1044 and cuadre.diferencia_ediciones == 1044
    assert cuadre.cuadra  # la diferencia la avisa la alineación, no el cuadre


def test_una_partida_mal_leida_si_descuadra_aunque_haya_ediciones():
    silla = (_item("SILLA", 100, 45, 0, "SILLAS", cantidad_nueva=120))
    todas = [silla, (_item("MESA", 10, 250, 1))]
    base = alineacion.base_sistema(todas)
    totales = servicio.totales(todas, [], None, base)
    assert not servicio.cuadre(todas, [], totales["total"], 7500, None, base).cuadra  # el PDF decía 7,500


def test_esta_alineada_en_la_lista():
    fila = {"cantidad": "10", "cantidad_sistema": "10", "precio_unitario": "250", "precio_sistema": "250",
            "categoria": "MESAS", "categoria_sistema": "MESAS", "origen": "sistema", "eliminada": False}
    assert alineacion.esta_alineada([fila])
    assert not alineacion.esta_alineada([{**fila, "cantidad": "12"}])
    assert not alineacion.esta_alineada([{**fila, "categoria": "COCKTAIL"}])
    assert not alineacion.esta_alineada([{**fila, "origen": "provista"}])
    assert not alineacion.esta_alineada([{**fila, "eliminada": True}])
    # Cotizaciones de antes de la migración: sin valores del sistema se toman como alineadas.
    assert alineacion.esta_alineada([{"cantidad": "10", "precio_unitario": "250", "categoria": "MESAS"}])


def test_seccion_normalizada_reusa_la_existente():
    assert seccion_normalizada("  ceremonia ", ["SILLAS", "CEREMONIA"]) == "CEREMONIA"
    assert seccion_normalizada("Cocktail  bar", ["SILLAS"]) == "Cocktail bar"


def test_mover_a_una_seccion_la_deja_al_final_de_esa_seccion():
    filas = [
        {"id": "a", "categoria": "SILLAS"}, {"id": "b", "categoria": "SILLAS"},
        {"id": "c", "categoria": "MESAS"}, {"id": "d", "categoria": "MESAS"}, {"id": "e", "categoria": "LUZ"},
    ]
    assert orden_tras_seccion(filas, ["a"], "MESAS") == ["b", "c", "d", "a", "e"]
    assert orden_tras_seccion(filas, ["a"], "NUEVA") is None  # sección nueva: se queda donde está
    assert orden_tras_seccion(filas, ["a", "b"], "LUZ") == ["c", "d", "e", "a", "b"]
