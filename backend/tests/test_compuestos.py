"""Artículos compuestos: varias partidas presentadas como un artículo, sin tocar precios ni totales."""

from io import BytesIO
from uuid import uuid4

from PIL import Image

from app.db.modelos import Compuesto, CotizacionDetalle, CotizacionItem, Imagen
from app.servicios import compuestos
from app.servicios import presentacion as pres
from app.servicios.proveedor_imagenes import ProveedorSimulado
from app.servicios.render_pdf import construir_contexto, renderizar_html


def _item(descripcion, categoria, cantidad, precio, orden, compuesto_id=None, codigo="COD", cargo=None):
    imagen_id = uuid4()
    return CotizacionItem(
        id=uuid4(),
        cotizacion_id=uuid4(),
        item_id=uuid4(),
        codigo_origen=codigo,
        descripcion_origen=descripcion,
        cantidad=cantidad,
        precio_unitario=precio,
        imagen_id=imagen_id,
        imagen=Imagen(id=imagen_id, ruta_storage=f"catalogo/X/{orden}.jpg", tipo="oficial"),
        tipo_item="catalogo",
        orden=orden,
        categoria=categoria,
        cargo=cargo,
        compuesto_id=compuesto_id,
        estado="sugerida",
        importe=round(cantidad * precio, 2),
    )


def _detalle(cantidad_base: float = 10) -> tuple[CotizacionDetalle, Compuesto]:
    generada = Imagen(id=uuid4(), ruta_storage="catalogo/MES/generadas/x.png", tipo="generada")
    compuesto = Compuesto(id=uuid4(), cotizacion_id=uuid4(), nombre="MESA REDONDA COMPLETA", imagen_id=generada.id, imagen=generada)
    items = [
        _item("SILLA TIFFANY BLANCA", "SILLAS", 100, 45, 0),
        _item("CUBIERTA REDONDA 1.80", "CUBIERTAS", 10, 150, 1, compuesto.id, codigo="CUB-180"),
        _item("MANTEL BLANCO", "MANTELERIA", 10, 80, 2),
        _item("BASE DE HIERRO NEGRA", "BASES", cantidad_base, 120, 3, compuesto.id, codigo="BAS-01"),
        _item("FLETE", "SERVICIOS", 1, 2000, 4, cargo="flete"),
    ]
    compuesto.item_ids = [items[1].id, items[3].id]
    subtotal = round(sum(i.importe for i in items if not i.cargo), 2)
    detalle = CotizacionDetalle(
        id=uuid4(),
        nombre_cliente="HACIENDA",
        referencia_externa="R-1",
        creado_por=uuid4(),
        creado_en="2026-10-01T10:00:00Z",
        actualizado_en="2026-10-01T10:00:00Z",
        items=items,
        compuestos=[compuesto],
        subtotal=subtotal,
        flete=2000,
        total=subtotal + 2000,
    )
    return detalle, compuesto


def test_renglones_juntan_el_compuesto_en_el_lugar_de_su_primera_partida():
    detalle, compuesto = _detalle()
    partidas = [i for i in detalle.items if not i.cargo]
    filas = compuestos.renglones(partidas, detalle.compuestos)
    assert [len(r.items) for r in filas] == [1, 2, 1]
    assert filas[1].compuesto is compuesto
    assert filas[1].cantidad_comun == 10
    assert filas[1].precio_unitario == 270  # 150 + 120 por mesa completa
    assert filas[1].importe == 2700  # la suma de las dos partidas: no cambia nada
    assert filas[1].imagen_id == compuesto.imagen_id and filas[1].es_render_conceptual


def test_sin_cantidad_comun_no_hay_precio_por_pieza():
    detalle, _ = _detalle(cantidad_base=5)
    fila = compuestos.renglones([i for i in detalle.items if not i.cargo], detalle.compuestos)[1]
    assert fila.cantidad_comun is None and fila.precio_unitario is None
    assert fila.importe == 1500 + 600


def test_las_partidas_del_compuesto_van_en_la_seccion_de_la_primera():
    detalle, _ = _detalle()
    seccion = compuestos.categoria_efectiva(detalle.items, detalle.compuestos)
    assert seccion[detalle.items[3].id] == "CUBIERTAS"
    assert seccion[detalle.items[2].id] == "MANTELERIA"


def test_nombre_por_defecto_y_prompt():
    detalle, _ = _detalle()
    partes = [detalle.items[1], detalle.items[3]]
    assert compuestos.nombre_por_defecto(partes) == "CUBIERTA REDONDA 1.80 + BASE DE HIERRO NEGRA"
    prompt = compuestos.prompt_compuesto(partes, "MESA COMPLETA", "mantel hasta el piso")
    assert "CUBIERTA REDONDA 1.80" in prompt and "BASE DE HIERRO NEGRA" in prompt
    assert "mantel hasta el piso" in prompt


def test_pdf_base_imprime_un_renglon_con_sus_componentes_y_los_mismos_totales():
    detalle, compuesto = _detalle()
    contexto = construir_contexto(detalle, {})
    assert contexto["total_items"] == 3
    renglon = contexto["items"][1]
    assert renglon.descripcion == "MESA REDONDA COMPLETA"
    assert renglon.cantidad == "10" and renglon.precio_unitario == "$270.00" and renglon.importe == "$2,700.00"
    assert [c[0] for c in renglon.componentes] == ["CUB-180", "BAS-01"]
    assert renglon.es_render_conceptual
    # El compuesto no parte la sección: no aparece "BASES".
    assert [s.titulo for s in contexto["secciones"]] == ["SILLAS", "CUBIERTAS", "MANTELERIA"]
    html = renderizar_html(contexto)
    assert "BASE DE HIERRO NEGRA" in html and "BAS-01" in html
    assert contexto["totales"][0][1] == f"${detalle.subtotal:,.2f}"


def test_presentacion_cuenta_el_compuesto_como_una_pieza():
    detalle, _ = _detalle()
    config = pres.config_por_defecto(detalle)
    vistas = pres.secciones_vista(config, detalle)
    assert [v.clave for v in vistas] == ["SILLAS", "CUBIERTAS", "MANTELERIA"]
    cubiertas = vistas[1]
    assert cubiertas.partidas == 1 and cubiertas.piezas == 10 and cubiertas.importe == 2700

    contexto = pres.construir_contexto(detalle, config, vistas, {}, set(), {})
    pieza = contexto["secciones"][1]["paginas"][0]["piezas"][0]
    assert pieza.nombre == "MESA REDONDA COMPLETA"
    assert pieza.componentes == ["10 × CUBIERTA REDONDA 1.80", "10 × BASE DE HIERRO NEGRA"]
    html = pres.renderizar_html(contexto)
    assert "10 × BASE DE HIERRO NEGRA" in html


def test_presentacion_sin_cantidad_comun_imprime_solo_el_importe():
    detalle, _ = _detalle(cantidad_base=5)
    config = pres.config_por_defecto(detalle)
    contexto = pres.construir_contexto(detalle, config, pres.secciones_vista(config, detalle), {}, set(), {})
    pieza = contexto["secciones"][1]["paginas"][0]["piezas"][0]
    assert pieza.cantidad == ""
    assert f'<p class="cifras">{pieza.importe}</p>' in pres.renderizar_html(contexto)


def _png(color) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (600, 300), color).save(buffer, format="PNG")
    return buffer.getvalue()


async def test_proveedor_simulado_combina_las_piezas():
    salidas = await ProveedorSimulado().generar_compuesto([_png((200, 0, 0)), _png((0, 0, 200))], "mesa", 2)
    assert len(salidas) == 2
    imagen = Image.open(BytesIO(salidas[0]))
    assert imagen.size == (1024, 1024)
