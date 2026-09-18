from datetime import datetime, timezone
from io import BytesIO
from uuid import uuid4

import pytest
from PIL import Image

from app.db.modelos import CotizacionDetalle, CotizacionItem, Imagen
from app.servicios.render_pdf import (
    a_data_uri,
    construir_contexto,
    formatear_cantidad,
    formatear_moneda,
    generar_pdf_cotizacion,
    renderizar_html,
)


def _png(color=(200, 200, 200)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (900, 700), color).save(buffer, format="PNG")
    return buffer.getvalue()


def _imagen(tipo: str) -> Imagen:
    return Imagen(id=uuid4(), item_id=uuid4(), ruta_storage=f"catalogo/X/{uuid4().hex}.png", tipo=tipo)


def _detalle() -> CotizacionDetalle:
    cot_id = uuid4()
    ahora = datetime.now(timezone.utc)
    oficial, generada = _imagen("oficial"), _imagen("generada")
    items = [
        CotizacionItem(
            id=uuid4(), cotizacion_id=cot_id, item_id=oficial.item_id, codigo_origen="SIL-001",
            descripcion_origen="Silla Tiffany blanca", cantidad=120, precio_unitario=45,
            imagen_id=oficial.id, imagen=oficial, tipo_item="catalogo", estado="sugerida", importe=5400, orden=0,
        ),
        CotizacionItem(
            id=uuid4(), cotizacion_id=cot_id, item_id=None, codigo_origen="",
            descripcion_origen="Letrero personalizado", cantidad=1, precio_unitario=2200,
            tipo_item="ad_hoc", estado="falta_imagen", importe=2200, orden=1,
        ),
        CotizacionItem(
            id=uuid4(), cotizacion_id=cot_id, item_id=generada.item_id, codigo_origen="MES-002",
            descripcion_origen="Mesa redonda 1.80 m", cantidad=12, precio_unitario=250,
            imagen_id=generada.id, imagen=generada, tipo_item="catalogo", es_render_conceptual=True,
            estado="render_conceptual", importe=3000, orden=2,
        ),
    ]
    return CotizacionDetalle(
        id=cot_id, nombre_cliente="Hacienda San Pedro", referencia_externa="COT-1", creado_por=uuid4(),
        creado_en=ahora, actualizado_en=ahora, items=items, total=10600, total_items=3, items_pendientes=1,
    )


def test_formatos():
    assert formatear_moneda(5400) == "$5,400.00"
    assert formatear_moneda(0.5) == "$0.50"
    assert formatear_cantidad(12) == "12"
    assert formatear_cantidad(2.5) == "2.50"


def test_data_uri_reduce_la_imagen():
    uri = a_data_uri(_png())
    assert uri.startswith("data:image/jpeg;base64,")
    assert len(uri) < 40_000


def test_html_contiene_marcadores_y_leyenda():
    detalle = _detalle()
    data_uris = {str(i.imagen.id): a_data_uri(_png()) for i in detalle.items if i.imagen}
    html = renderizar_html(construir_contexto(detalle, data_uris))

    assert "Hacienda San Pedro" in html and "COT-1" in html
    assert html.count("Sin imagen") == 1
    assert "Render conceptual" in html
    assert "sujeta a confirmación de producción" in html  # nota en el ítem
    assert "Sobre los renders conceptuales" in html  # leyenda al pie
    assert "$10,600.00" in html
    assert "Letrero personalizado" in html


def test_sin_render_conceptual_no_hay_leyenda():
    detalle = _detalle()
    detalle.items = [i for i in detalle.items if not i.es_render_conceptual]
    html = renderizar_html(construir_contexto(detalle, {}))
    assert "Sobre los renders conceptuales" not in html
    assert html.count("Sin imagen") == 2  # sin data URIs todo queda como marcador


class StorageFalso:
    bucket_imagenes = "imagenes"

    def __init__(self):
        self.descargas = []

    async def descargar(self, bucket, ruta):
        self.descargas.append(ruta)
        return _png()


async def test_genera_pdf_desde_detalle():
    """Prueba de punta a punta del render. Requiere las librerías nativas de WeasyPrint."""
    from tests.conftest import requerir_weasyprint

    requerir_weasyprint()
    detalle = _detalle()
    storage = StorageFalso()
    pdf = await generar_pdf_cotizacion(detalle, storage)
    assert pdf[:5] == b"%PDF-"
    assert len(storage.descargas) == 2
    assert len(pdf) > 5_000
