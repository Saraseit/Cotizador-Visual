"""Cómo se imprime la fecha del evento en la propuesta.

Un día suelto va completo. En un rango sólo se repite lo que haga falta: el año se dice una vez, y
en español el mes también cuando es el mismo, que es como lo diría una persona.
"""

from __future__ import annotations

from datetime import date

SEPARADOR = {"es": "al", "en": "to"}


def _dia(fecha: date, idioma: str) -> str:
    return fecha.strftime("%m/%d/%Y") if idioma == "en" else fecha.strftime("%d/%m/%Y")


def _inicio_de_rango(inicio: date, fin: date, idioma: str) -> str:
    """El primer día sin lo que ya dirá el segundo."""
    if idioma == "en":
        return inicio.strftime("%m/%d") if inicio.year == fin.year else _dia(inicio, idioma)
    if inicio.year == fin.year and inicio.month == fin.month:
        return f"{inicio.day:02d}"
    if inicio.year == fin.year:
        return inicio.strftime("%d/%m")
    return _dia(inicio, idioma)


def texto_evento(inicio: date | None, fin: date | None, idioma: str = "es") -> str:
    """'28/11/2026', '28 al 30/11/2026', '28/11 al 02/12/2026' o '' si no hay fecha."""
    if inicio is None:
        return ""
    if fin is None or fin == inicio:
        return _dia(inicio, idioma)
    separador = SEPARADOR.get(idioma, SEPARADOR["es"])
    return f"{_inicio_de_rango(inicio, fin, idioma)} {separador} {_dia(fin, idioma)}"
