"""Formato del PDF de la propuesta base: notas, campos extra, título y logotipo."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.db.modelos import (
    NOTAS_POR_DEFECTO,
    AjustesPropuesta,
    AjustesPropuestaEntrada,
    CampoPropuesta,
    CotizacionDetalle,
)
from app.servicios import ajustes_propuesta as servicio
from app.servicios.render_pdf import construir_contexto, renderizar_html

EVENTO = CampoPropuesta(id="evento", etiqueta="Fecha del evento", tipo="fecha")
MONTAJE = CampoPropuesta(id="montaje", etiqueta="Hora de montaje", tipo="hora", predeterminado="09:00")
LUGAR = CampoPropuesta(id="lugar", etiqueta="Lugar", tipo="texto")


def _detalle(campos=None) -> CotizacionDetalle:
    ahora = datetime.now(UTC)
    return CotizacionDetalle(
        id=uuid4(), nombre_cliente="HACIENDA", referencia_externa="R-1", creado_por=uuid4(),
        creado_en=ahora, actualizado_en=ahora, campos=campos or {},
    )


def test_por_defecto_salen_las_notas_de_siempre_y_el_logotipo_de_la_marca():
    html = renderizar_html(construir_contexto(_detalle(), {}))
    assert "IMPORTANTE DE LEER" in html and "Los anticipos no son reembolsables." in html
    assert "<h2>Notas</h2>" in html
    assert 'class="logotipo" src="data:image/png;base64,' in html
    assert "Propuesta de mobiliario" in html


def test_titulo_subtitulo_y_notas_personalizados():
    ajustes = AjustesPropuesta(titulo="Cotización de renta", subtitulo="Mérida, Yuc.", notas_titulo="", notas="Línea uno\n\nLínea dos")
    contexto = construir_contexto(_detalle(), {}, ajustes=ajustes, marca={})
    html = renderizar_html(contexto)
    assert "Cotización de renta" in html and "Mérida, Yuc." in html
    assert contexto["notas"] == ["Línea uno", "", "Línea dos"]
    assert "<h2>" not in html.split('class="notas"')[1].split("</section>")[0]
    assert 'class="logotipo"' not in html  # sin imágenes de marca


def test_sin_notas_no_hay_seccion():
    html = renderizar_html(construir_contexto(_detalle(), {}, ajustes=AjustesPropuesta(notas="")))
    assert 'class="notas"' not in html


def test_campos_usan_el_valor_o_el_predeterminado_y_se_formatean():
    ajustes = AjustesPropuesta(campos=[EVENTO, MONTAJE, LUGAR])
    assert servicio.campos_impresos(ajustes, {"evento": "2026-11-20"}) == [
        ("Fecha del evento", "20/11/2026"),
        ("Hora de montaje", "09:00"),
    ]
    assert servicio.campos_impresos(ajustes, {"evento": "2026-11-20", "montaje": "18:30"}, "en") == [
        ("Fecha del evento", "11/20/2026"),
        ("Hora de montaje", "6:30 PM"),
    ]
    html = renderizar_html(construir_contexto(_detalle({"lugar": "Hacienda Xcanatún"}), {}, ajustes=ajustes))
    assert "Lugar</strong> Hacienda Xcanatún" in html


def test_validar_valores():
    assert servicio.validar_valor(EVENTO, " 2026-11-20 ") == "2026-11-20"
    assert servicio.validar_valor(MONTAJE, "") == ""
    for campo, valor in ((EVENTO, "20/11/2026"), (EVENTO, "2026-02-31"), (MONTAJE, "25:00"), (MONTAJE, "9am")):
        with pytest.raises(ValueError):
            servicio.validar_valor(campo, valor)


def test_campos_repetidos_no_se_aceptan():
    with pytest.raises(ValidationError):
        AjustesPropuestaEntrada(campos=[LUGAR, LUGAR])


def test_las_notas_por_defecto_son_las_del_sistema():
    assert NOTAS_POR_DEFECTO.splitlines()[0] == "IMPORTANTE DE LEER"
    assert len(NOTAS_POR_DEFECTO.splitlines()) == 7
