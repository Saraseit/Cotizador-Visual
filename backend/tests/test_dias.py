"""Días de renta y días cobrados.

El sistema principal multiplica el mobiliario por DIAS y cobra flete y montaje una vez:
SubTotal = mobiliario × DIAS + flete + montaje. Los números son los de una cotización real de
3 días (sillas $8,700 por día, flete $1,300, montaje $660, SubTotal $28,060, IVA $4,489.60).
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.db.modelos import CotizacionDetalle, CotizacionItem, DatosEvento
from app.servicios import alineacion
from app.servicios import compuestos as servicio
from app.servicios.parser_export import _leer_metadatos_pdf, cargar_mapeo, leer_dias, leer_fecha
from app.servicios.render_pdf import construir_contexto, renderizar_html

SUBTOTAL_SISTEMA = 28_060.00
IVA_SISTEMA = 4_489.60


def _item(descripcion, cantidad, precio, orden, cargo=None, categoria="SILLAS"):
    return CotizacionItem(
        id=uuid4(), cotizacion_id=uuid4(), codigo_origen="", descripcion_origen=descripcion, tipo_item="catalogo",
        orden=orden, origen="sistema", cargo=cargo, categoria=categoria,
        cantidad=cantidad, precio_unitario=precio, cantidad_sistema=cantidad, precio_sistema=precio,
        categoria_sistema=categoria, importe=round(cantidad * precio, 2),
    )


def _partidas():
    return [
        _item("SILLA CROSSBACK", 100, 87, 0),  # $8,700 por día
        _item("FLETE", 1, 1300, 1, cargo="flete", categoria="W FLETES"),
        _item("TURNOS MONTAJE Y DESMONTAJE", 1, 660, 2, cargo="montaje", categoria="MONTAJE"),
    ]


# --- La cuenta del sistema ----------------------------------------------------------

def test_el_mobiliario_se_multiplica_por_los_dias_y_los_cargos_no():
    todas = _partidas()
    base = alineacion.base_sistema(todas, dias=3)
    assert base == SUBTOTAL_SISTEMA

    totales = servicio.totales(todas, [], IVA_SISTEMA, base, dias=3)
    assert totales["subtotal_por_dia"] == 8_700
    assert totales["subtotal"] == 26_100
    assert (totales["flete"], totales["montaje"]) == (1_300, 660)
    assert totales["iva"] == IVA_SISTEMA  # sin cambios: el IVA exacto del PDF
    assert totales["total"] == 32_549.60


def test_con_los_dias_del_sistema_la_propuesta_cuadra():
    todas = _partidas()
    base = alineacion.base_sistema(todas, dias=3)
    total = servicio.totales(todas, [], IVA_SISTEMA, base, dias=3)["total"]
    cuadre = servicio.cuadre(todas, [], total, SUBTOTAL_SISTEMA, IVA_SISTEMA, base, dias=3)
    assert cuadre.cuadra
    assert cuadre.suma_partidas == SUBTOTAL_SISTEMA
    assert alineacion.alineacion(todas, 3, 3).alineada


def test_sin_dias_la_tasa_de_iva_salia_mal():
    """El error de antes: dividir el IVA del sistema entre la suma por día daba un 42 %."""
    todas = _partidas()
    assert alineacion.tasa_iva(IVA_SISTEMA, alineacion.base_sistema(todas, dias=3)) == pytest.approx(0.16)
    assert alineacion.tasa_iva(IVA_SISTEMA, alineacion.base_sistema(todas)) == pytest.approx(0.4212, abs=1e-4)


def test_promocion_se_rentan_tres_y_se_cobra_uno():
    """En el sistema quedó DIAS 3; en ProVista se cobra uno. La propuesta lo refleja y avisa que el
    sistema todavía cobra tres (es un cambio por aplicar allá, no un error de lectura)."""
    todas = _partidas()
    base = alineacion.base_sistema(todas, dias=3)
    totales = servicio.totales(todas, [], IVA_SISTEMA, base, dias=1)
    assert totales["subtotal"] == 8_700
    assert totales["iva"] == round((8_700 + 1_960) * 0.16, 2)

    resultado = alineacion.alineacion(todas, dias_cobrados=1, dias_sistema=3)
    assert not resultado.alineada
    assert [(c.tipo, c.antes, c.despues) for c in resultado.cambios] == [("dias", 3, 1)]
    assert resultado.diferencia_importe == -17_400  # 8,700 × 2 días que ya no se cobran

    cuadre = servicio.cuadre(todas, [], totales["total"], SUBTOTAL_SISTEMA, IVA_SISTEMA, base, dias=1)
    assert cuadre.cuadra  # la diferencia la explica el cambio de días: la avisa la alineación
    assert not alineacion.esta_alineada([], dias_cobrados=1, dias_sistema=3)


def test_un_dia_es_lo_de_siempre():
    todas = _partidas()
    con_dias = servicio.totales(todas, [], None, alineacion.base_sistema(todas, 1), dias=1)
    sin_dias = servicio.totales(todas, [], None, alineacion.base_sistema(todas))
    assert con_dias == sin_dias


# --- Lo que trae el export ------------------------------------------------------------

def test_lee_fecha_vendedor_y_dias_del_encabezado():
    """El texto tal como lo saca pdfplumber de un export del sistema (datos inventados)."""
    texto = (
        "Captura:mar. 27 octubre, 26 Cotización\n"
        "Atendio:SAMUEL\n"
        "Cliente: CLIENTE DE PRUEBA Teléfono: 9990000000\n"
        "Fecha de evento: viernes 30 octubre 2026 Lugar: CASA EN EL CENTRO\n"
        "Tipo de evento: SOC - otro\n"
        "2.- Los pedidos requieren un 50% de anticipo y el resto 2 días antes del evento.\n"
        "DIAS: 3.0 Total: $4,535.60\n"
    )
    mapeo = cargar_mapeo("fixtures/mapeo_columnas.json")
    leido = _leer_metadatos_pdf([], texto, mapeo["pdf"]["metadatos"])
    assert leido["vendedor"] == "SAMUEL"
    assert str(leer_fecha(leido["fecha_evento"])) == "2026-10-30"
    assert float(leer_dias(leido["dias"])) == 3.0


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("viernes 30 octubre 2026", "2026-10-30"),
        ("sábado 03 octubre 2026", "2026-10-03"),
        ("miércoles 04 noviembre 2026", "2026-11-04"),
        ("30 de octubre de 2026", "2026-10-30"),
        ("30/10/2026", "2026-10-30"),
        ("2026-10-30", "2026-10-30"),
        ("31 febrero 2026", None),  # imposible: mejor sin fecha que con una inventada
        ("NO DEFINIDO", None),
    ],
)
def test_leer_fecha(texto, esperado):
    fecha = leer_fecha(texto)
    assert (str(fecha) if fecha else None) == esperado


# --- Lo que se captura en Revisar ---------------------------------------------------------

def test_dias_cobrados_vacio_son_los_de_renta():
    datos = DatosEvento(dias_renta=3)
    assert datos.dias_cobrados is None


def test_los_dias_tienen_que_ser_positivos():
    with pytest.raises(ValidationError):
        DatosEvento(dias_renta=0)
    with pytest.raises(ValidationError):
        DatosEvento(dias_renta=3, dias_cobrados=0)


# --- Lo que sale impreso -----------------------------------------------------------------

def _detalle(dias_renta, dias_cobrados=None):
    ahora = datetime.now(timezone.utc)
    items = _partidas()
    cobrados = dias_renta if dias_cobrados is None else dias_cobrados
    totales = servicio.totales(items, [], None, dias=cobrados)
    return CotizacionDetalle(
        id=uuid4(), nombre_cliente="CLIENTE DE PRUEBA", referencia_externa="1", creado_por=uuid4(),
        creado_en=ahora, actualizado_en=ahora, items=items, vendedor="SAMUEL",
        dias_renta=dias_renta, dias_cobrados=dias_cobrados, **totales,
    )


def test_el_pdf_muestra_la_cuenta_por_dia():
    html = renderizar_html(construir_contexto(_detalle(3), {}))
    assert "Vendedor" in html and "SAMUEL" in html
    assert "Días de renta" in html
    assert "Días cobrados" not in html  # son los mismos: no hace falta decirlo dos veces
    assert "Importe por día" in html
    assert "Mobiliario por día" in html and "$8,700.00" in html
    assert "Subtotal mobiliario · 3 días" in html and "$26,100.00" in html


def test_el_pdf_hace_visible_la_promocion():
    html = renderizar_html(construir_contexto(_detalle(3, dias_cobrados=1), {}))
    assert "Días de renta" in html and "Días cobrados" in html
    assert "Mobiliario por día" not in html  # se cobra un día: la cuenta de siempre
    assert "Subtotal mobiliario" in html and "$8,700.00" in html


def test_un_dia_sin_cambios_en_el_pdf():
    html = renderizar_html(construir_contexto(_detalle(1), {}))
    assert "Importe por día" not in html and "Mobiliario por día" not in html
