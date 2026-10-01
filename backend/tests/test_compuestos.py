"""Artículos compuestos: varias partidas presentadas como un artículo, su precio y el cuadre con el PDF."""

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
    detalle, _ = _detalle()
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


# ---------------------------------------------------------------------------
# Precio del compuesto y cuadre contra el PDF del sistema
# ---------------------------------------------------------------------------


def _con_precio(modo: str, **datos) -> tuple[CotizacionDetalle, Compuesto]:
    detalle, compuesto = _detalle()
    compuesto.precio_modo = modo  # type: ignore[assignment]
    for clave, valor in datos.items():
        setattr(compuesto, clave, valor)
    return detalle, compuesto


def _renglon(detalle):
    return compuestos.renglones([i for i in detalle.items if not i.cargo], detalle.compuestos)[1]


def test_se_queda_el_precio_de_una_partida():
    detalle, compuesto = _detalle()
    compuesto.precio_modo, compuesto.precio_item_id = "partida", detalle.items[1].id  # la cubierta
    renglon = _renglon(detalle)
    assert (renglon.cantidad, renglon.precio_unitario, renglon.importe) == (10, 150, 1500)
    assert renglon.importe_partidas == 2700 and renglon.precio_cambiado


def test_precio_manual_por_articulo():
    detalle, _ = _con_precio("manual", precio_manual=200)
    renglon = _renglon(detalle)
    assert (renglon.cantidad, renglon.precio_unitario, renglon.importe) == (10, 200, 2000)


def test_partida_ajena_vuelve_a_la_suma():
    detalle, _ = _con_precio("partida", precio_item_id=uuid4())
    assert _renglon(detalle).modo == "suma" and _renglon(detalle).importe == 2700


def test_con_la_suma_cuadra_con_el_documento():
    detalle, _ = _detalle()
    totales = compuestos.totales(detalle.items, detalle.compuestos, 1600)
    cuadre = compuestos.cuadre(detalle.items, detalle.compuestos, totales["total"], 10_000, 1600)
    assert totales["subtotal"] == 8000 and totales["iva"] == 1600
    assert cuadre.cuadra and cuadre.diferencia == 0 and cuadre.ajustes == []


def test_otro_precio_cambia_total_ajusta_iva_y_no_cuadra():
    detalle, _ = _con_precio("manual", precio_manual=200)  # 2,000 en vez de 2,700
    totales = compuestos.totales(detalle.items, detalle.compuestos, 1600)
    assert totales["subtotal"] == 7300
    assert totales["iva"] == round(1600 * 9300 / 10000, 2)  # base del documento: 8,000 + 2,000 de flete
    cuadre = compuestos.cuadre(detalle.items, detalle.compuestos, totales["total"], 10_000, 1600)
    assert not cuadre.cuadra
    assert cuadre.total_documento == 11_600 and cuadre.diferencia == round(totales["total"] - 11_600, 2)
    assert [(a.nombre, a.importe_partidas, a.importe) for a in cuadre.ajustes] == [("MESA REDONDA COMPLETA", 2700, 2000)]


def test_partida_mal_leida_no_cuadra_aunque_no_haya_compuestos():
    detalle, _ = _detalle()
    # El PDF dice SubTotal 10,500 pero las partidas leídas (mobiliario y flete) suman 10,000.
    totales = compuestos.totales(detalle.items, detalle.compuestos, None)
    cuadre = compuestos.cuadre(detalle.items, detalle.compuestos, totales["total"], 10_500, None)
    assert not cuadre.cuadra and cuadre.diferencia == -500 and cuadre.ajustes == []


def test_sin_subtotal_del_documento_se_compara_con_las_partidas():
    detalle, _ = _detalle()
    totales = compuestos.totales(detalle.items, detalle.compuestos, None)
    assert compuestos.cuadre(detalle.items, detalle.compuestos, totales["total"], None, None).cuadra


def test_pdf_base_con_otro_precio_no_muestra_importes_de_las_partidas():
    detalle, _ = _con_precio("manual", precio_manual=200)
    detalle.subtotal = 7300
    renglon = construir_contexto(detalle, {})["items"][1]
    assert renglon.importe == "$2,000.00" and renglon.precio_unitario == "$200.00"
    assert all(c[3] == "" for c in renglon.componentes)


def test_presentacion_usa_el_importe_presentado():
    detalle, _ = _con_precio("manual", precio_manual=200)
    config = pres.config_por_defecto(detalle)
    vistas = pres.secciones_vista(config, detalle)
    assert vistas[1].importe == 2000


def test_la_lista_de_propuestas_trae_el_cuadre():
    from app.routers.cotizaciones import _resumen_desde_fila

    cotizacion, cubierta, base, compuesto = (str(uuid4()) for _ in range(4))

    def partida(item_id, precio, orden):
        return {"id": item_id, "imagen_id": None, "cargo": None, "compuesto_id": compuesto, "cantidad": "10",
                "precio_unitario": precio, "orden": orden, "tipo_item": "catalogo"}

    fila = {
        "id": cotizacion, "nombre_cliente": "X", "referencia_externa": "R", "creado_por": cotizacion,
        "creado_en": "2026-10-01T00:00:00Z", "actualizado_en": "2026-10-01T00:00:00Z",
        "iva_documento": "432.00", "subtotal_documento": "2700.00",
        "cotizacion_items": [partida(cubierta, "150", 0), partida(base, "120", 1)],
        "cotizacion_compuestos": [
            {"id": compuesto, "nombre": "MESA COMPLETA", "imagen_id": None, "precio_modo": "partida", "precio_item_id": cubierta,
             "precio_manual": None}
        ],
    }
    resumen = _resumen_desde_fila(fila)
    assert not resumen.cuadre.cuadra and resumen.cuadre.diferencia == -1392  # (1,500 + IVA) contra (2,700 + IVA)
    assert [a.nombre for a in resumen.cuadre.ajustes] == ["MESA COMPLETA"]
    fila["cotizacion_compuestos"][0]["precio_modo"] = "suma"
    assert _resumen_desde_fila(fila).cuadre.cuadra
