"""Comprobación de render dentro de la imagen de Docker (la corre CI, sin Supabase).

Renderiza el PDF base y una presentación editorial mínima: así se detecta si a la imagen le falta
una fuente, un logo o la plantilla.

Uso:  python scripts/prueba_render_imagen.py
"""

from __future__ import annotations

import sys
from uuid import uuid4

from app.db.modelos import CotizacionDetalle, CotizacionItem
from app.servicios import presentacion as pres
from app.servicios.render_pdf import html_a_pdf


def _detalle() -> CotizacionDetalle:
    item = CotizacionItem(
        id=uuid4(),
        cotizacion_id=uuid4(),
        codigo_origen="SIL-001",
        descripcion_origen="SILLA TIFFANY BLANCA (INCLUYE MOÑO)",
        cantidad=120,
        precio_unitario=45,
        tipo_item="catalogo",
        orden=0,
        categoria="SILLAS",
        estado="falta_imagen",
        importe=5400,
    )
    return CotizacionDetalle(
        id=uuid4(),
        nombre_cliente="PRUEBA",
        referencia_externa="0",
        creado_por=uuid4(),
        archivo_origen_ruta="x",
        estado="revision",
        creado_en="2026-09-22T10:00:00Z",
        actualizado_en="2026-09-22T10:00:00Z",
        items=[item],
        subtotal=5400,
        flete=0,
        montaje=0,
        iva=None,
        total=5400,
        total_items=1,
        items_pendientes=1,
    )


def main() -> int:
    base = html_a_pdf('<p style="font-family: IBM Plex Sans">Prueba</p>')
    assert base.startswith(b"%PDF-"), "el PDF base no se generó"
    print(f"PDF base OK, {len(base)} bytes")

    detalle = _detalle()
    config = pres.config_por_defecto(detalle)
    for tipografia in ("everett", "bebas"):  # 'everett' cae a Public Sans si no están sus archivos
        config.tipografia_titulos = tipografia
        vistas = pres.secciones_vista(config, detalle)
        contexto = pres.construir_contexto(detalle, config, vistas, {}, set(), {})
        editorial = html_a_pdf(pres.renderizar_html(contexto))
        assert editorial.startswith(b"%PDF-"), "la presentación editorial no se generó"
        assert contexto["monograma"].startswith("data:image/png;base64,"), "falta el monograma de marca"
        print(f"Presentación editorial OK con títulos '{tipografia}', {len(editorial)} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
