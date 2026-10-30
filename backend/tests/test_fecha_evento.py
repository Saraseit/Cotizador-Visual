"""La fecha que se imprime en la propuesta es la del evento, no la del día en que se generó el PDF."""

from datetime import date, datetime

import pytest
from pydantic import ValidationError

from app.db.modelos import FechaEvento
from app.servicios import fechas


@pytest.mark.parametrize(
    ("inicio", "fin", "idioma", "esperado"),
    [
        (date(2026, 11, 28), None, "es", "28/11/2026"),
        (date(2026, 11, 28), None, "en", "11/28/2026"),
        (date(2026, 11, 28), date(2026, 11, 28), "es", "28/11/2026"),  # mismo día = no es rango
        (date(2026, 11, 28), date(2026, 11, 30), "es", "28 al 30/11/2026"),
        (date(2026, 11, 28), date(2026, 12, 2), "es", "28/11 al 02/12/2026"),
        (date(2026, 12, 30), date(2027, 1, 2), "es", "30/12/2026 al 02/01/2027"),
        (date(2026, 11, 28), date(2026, 11, 30), "en", "11/28 to 11/30/2026"),
        (date(2026, 12, 30), date(2027, 1, 2), "en", "12/30/2026 to 01/02/2027"),
        (None, None, "es", ""),
        (None, date(2026, 11, 30), "es", ""),  # sin inicio no hay nada que decir
    ],
)
def test_texto_evento(inicio: date | None, fin: date | None, idioma: str, esperado: str) -> None:
    assert fechas.texto_evento(inicio, fin, idioma) == esperado


def test_el_rango_al_reves_no_pasa() -> None:
    with pytest.raises(ValidationError, match="terminar antes de empezar"):
        FechaEvento(fecha_evento=date(2026, 11, 30), fecha_evento_fin=date(2026, 11, 28))


def test_el_ultimo_dia_necesita_el_primero() -> None:
    with pytest.raises(ValidationError, match="hace falta el primero"):
        FechaEvento(fecha_evento=None, fecha_evento_fin=date(2026, 11, 30))


def test_sin_fechas_es_valido() -> None:
    """Quitar la fecha tiene que poder hacerse: la propuesta sale sin fecha, no rota."""
    vacio = FechaEvento()
    assert vacio.fecha_evento is None and vacio.fecha_evento_fin is None


def test_el_pdf_imprime_la_del_evento_y_no_la_de_hoy() -> None:
    from app.servicios.render_pdf import construir_contexto, renderizar_html
    from tests.test_render_pdf import _detalle  # la misma cotización que el resto de pruebas de PDF

    detalle = _detalle()
    detalle.fecha_evento = date(2026, 11, 28)
    detalle.fecha_evento_fin = date(2026, 11, 30)
    html = renderizar_html(construir_contexto(detalle, {}))

    assert "Fecha del evento" in html
    assert "28 al 30/11/2026" in html
    assert datetime.now().strftime("%d/%m/%Y") not in html


def test_sin_fecha_el_encabezado_no_trae_renglón_de_fecha() -> None:
    """Mejor sin fecha que con la de hoy, que al cliente le dice otra cosa."""
    from app.servicios.render_pdf import construir_contexto, renderizar_html
    from tests.test_render_pdf import _detalle

    html = renderizar_html(construir_contexto(_detalle(), {}))

    assert "Fecha del evento" not in html
    assert datetime.now().strftime("%d/%m/%Y") not in html
