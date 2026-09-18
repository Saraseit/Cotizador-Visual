"""Alta rápida del catálogo a partir de texto pegado (una línea por ítem).

Formato por línea, separado por tabulador, punto y coma, barra vertical o coma (se detecta
el separador más probable en todo el texto):

    codigo; nombre; categoria; descripcion; medidas; costo_reposicion; etiqueta1|etiqueta2

Sólo `codigo` es obligatorio. Si la primera línea es un encabezado ("codigo", "clave"...) se
ignora. Los códigos repetidos se quedan con la última línea.
"""

from __future__ import annotations

import re
from typing import Any

from app.servicios.matching import normalizar_codigo
from app.servicios.parser_export import ErrorParser, a_decimal, normalizar_texto

ENCABEZADOS = {"codigo", "clave", "sku", "code"}
SEPARADORES = ("\t", ";", "|", ",")


def detectar_separador(texto: str) -> str:
    """Tabulador > punto y coma > barra > coma, según cuál aparezca en el texto."""
    for separador in SEPARADORES:
        if separador in texto:
            return separador
    return ","


def parsear_texto_catalogo(texto: str) -> tuple[list[dict[str, Any]], list[str]]:
    separador = detectar_separador(texto)
    filas: dict[str, dict[str, Any]] = {}
    errores: list[str] = []

    for numero, linea in enumerate(texto.splitlines(), start=1):
        if not linea.strip():
            continue
        partes = [p.strip().strip('"') for p in linea.split(separador)]
        if numero == 1 and partes and normalizar_texto(partes[0]) in ENCABEZADOS:
            continue

        codigo = normalizar_codigo(partes[0]) if partes else ""
        if not codigo:
            errores.append(f"Línea {numero}: falta el código.")
            continue

        def campo(indice: int) -> str:
            return partes[indice] if len(partes) > indice else ""

        fila: dict[str, Any] = {
            "codigo": codigo,
            "nombre": campo(1) or codigo,
            "categoria": campo(2),
            "descripcion": campo(3),
            "medidas": campo(4),
            "activo": True,
        }
        costo = campo(5)
        if costo:
            if not re.search(r"\d", costo):
                errores.append(f"Línea {numero}: costo de reposición '{costo}' no es un número; se omitió.")
            else:
                try:
                    fila["costo_reposicion"] = float(a_decimal(costo))
                except ErrorParser:
                    errores.append(f"Línea {numero}: costo de reposición '{costo}' no es un número; se omitió.")
        etiquetas = campo(6)
        if etiquetas:
            # Cuando el separador es la barra, las etiquetas van separadas por coma.
            sep_etiquetas = "," if separador == "|" else "|"
            fila["etiquetas"] = sorted({e.strip().lower() for e in etiquetas.split(sep_etiquetas) if e.strip()})
        filas[codigo] = fila

    return list(filas.values()), errores
