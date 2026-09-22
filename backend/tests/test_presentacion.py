"""Presentación editorial: secciones, concentrado, títulos, prompt de montaje y render."""

from io import BytesIO
from uuid import uuid4

import pytest
from PIL import Image

from app.db.modelos import (
    ConfigPresentacion,
    CotizacionDetalle,
    CotizacionItem,
    Imagen,
    Paleta,
    SeccionPresentacion,
)
from app.servicios import presentacion as pres


def _item(descripcion, categoria, cantidad, precio, orden, cargo=None, con_imagen=True):
    imagen_id = uuid4() if con_imagen and not cargo else None
    return CotizacionItem(
        id=uuid4(),
        cotizacion_id=uuid4(),
        codigo_origen="COD",
        descripcion_origen=descripcion,
        cantidad=cantidad,
        precio_unitario=precio,
        imagen_id=imagen_id,
        tipo_item="catalogo",
        orden=orden,
        categoria=categoria,
        cargo=cargo,
        imagen=Imagen(id=imagen_id, ruta_storage=f"catalogo/X/{orden}.jpg", tipo="oficial") if imagen_id else None,
        estado="sugerida" if imagen_id else "falta_imagen",
        importe=round(cantidad * precio, 2),
    )


def _detalle(iva: float | None = 8361.6) -> CotizacionDetalle:
    items = [
        _item("SILLA TIFFANY BLANCA (INCLUYE MOÑO)", "SILLAS", 120, 45, 0),
        _item("SILLA CROSSBACK NATURAL", "SILLAS", 80, 65, 1, con_imagen=False),
        _item("MESA REDONDA DE 1.80", "MESA BANQUETE", 12, 250, 2),
        _item("FLETE A HACIENDA", "SERVICIOS", 1, 3000, 3, cargo="flete"),
        _item("MONTAJE Y DESMONTAJE", "SERVICIOS", 1, 2500, 4, cargo="montaje"),
    ]
    subtotal = round(sum(i.importe for i in items if not i.cargo), 2)
    return CotizacionDetalle(
        id=uuid4(),
        nombre_cliente="HACIENDA SAN PEDRO",
        referencia_externa="12345",
        creado_por=uuid4(),
        archivo_origen_ruta="x",
        estado="revision",
        creado_en="2026-09-22T10:00:00Z",
        actualizado_en="2026-09-22T10:00:00Z",
        items=items,
        subtotal=subtotal,
        flete=3000,
        montaje=2500,
        iva=iva,
        total=round(subtotal + 5500 + (iva or 0), 2),
        total_items=3,
        items_pendientes=1,
    )


def test_secciones_excluyen_cargos_y_siguen_el_orden():
    detalle = _detalle()
    vistas = pres.secciones_vista(pres.config_por_defecto(detalle), detalle)
    assert [v.clave for v in vistas] == ["SILLAS", "MESA BANQUETE"]
    sillas = vistas[0]
    assert (sillas.titulo, sillas.partidas, sillas.piezas, sillas.con_imagen) == ("SILLAS", 2, 200, 1)
    assert sillas.importe == 120 * 45 + 80 * 65


def test_la_cotizacion_manda_sobre_la_config_guardada():
    """Si la cotización cambió, se respetan los títulos guardados pero no aparecen secciones fantasma."""
    detalle = _detalle()
    config = ConfigPresentacion(
        secciones=[
            SeccionPresentacion(clave="SILLAS", titulo="CÓCTEL", texto="hola", incluir=False),
            SeccionPresentacion(clave="YA NO EXISTE", titulo="VIEJA"),
        ]
    )
    vistas = pres.secciones_vista(config, detalle)
    assert [v.clave for v in vistas] == ["SILLAS", "MESA BANQUETE"]
    assert (vistas[0].titulo, vistas[0].incluir) == ("CÓCTEL", False)
    assert vistas[1].titulo == "MESA BANQUETE"  # sección nueva: título por defecto


def test_config_invalida_cae_a_la_de_por_defecto():
    detalle = _detalle()
    config = pres.leer_config({"paleta": {"fondo": "rojo"}}, detalle)
    assert config.paleta.fondo == "#FFFCF7"
    assert config.evento == "HACIENDA SAN PEDRO"


def test_titulos_gigantes_caben_en_el_ancho():
    ancho = pres.ANCHO_PAGINA - 2 * pres.MARGEN
    for texto in ("SILLAS", "MESA BANQUETE", "LOUNGE Y BARRAS", "DECORACIÓN DE CEREMONIA CIVIL"):
        tamano = pres.tamano_titulo(texto, ancho, 170, "everett")
        assert pres.ancho_em(texto.upper(), "everett") * tamano <= ancho + 0.5
        assert 18 <= tamano <= 170
    # Bebas Neue es condensada: el mismo título puede ir más grande.
    assert pres.tamano_titulo("SILLAS", ancho, 170, "bebas") >= pres.tamano_titulo("SILLAS", ancho, 170, "everett")


def _contexto(detalle, config=None, precios=True):
    config = config or pres.config_por_defecto(detalle)
    config.mostrar_precios = precios
    vistas = pres.secciones_vista(config, detalle)
    return pres.construir_contexto(detalle, config, vistas, {}, set(), {})


def test_concentrado_lleva_todas_las_secciones_y_los_totales():
    detalle = _detalle()
    contexto = _contexto(detalle)
    assert [f["titulo"] for f in contexto["concentrado"]] == ["SILLAS", "MESA BANQUETE"]
    assert [e for e, _ in contexto["totales"]] == ["Subtotal mobiliario", "Flete", "Montaje", "IVA"]
    assert contexto["total"] == "$27,461.60"  # 13,600 de mobiliario + 5,500 de cargos + IVA
    assert contexto["mas_iva"] is False


def test_sin_iva_el_total_dice_mas_iva():
    contexto = _contexto(_detalle(iva=None))
    assert [e for e, _ in contexto["totales"]] == ["Subtotal mobiliario", "Flete", "Montaje"]
    assert contexto["mas_iva"] is True


def test_ocultar_precios_quita_los_importes_del_html():
    detalle = _detalle()
    con_precios = pres.renderizar_html(_contexto(detalle, precios=True))
    sin_precios = pres.renderizar_html(_contexto(detalle, precios=False))
    assert "$5,400.00" in con_precios and "Inversión" in con_precios
    assert "$" not in sin_precios and "Resumen" in sin_precios
    assert "200 piezas" in sin_precios  # las piezas sí se muestran
    assert "La propuesta considera flete y montaje." in sin_precios


def test_la_seccion_excluida_no_se_imprime_pero_sigue_en_el_concentrado():
    detalle = _detalle()
    config = pres.config_por_defecto(detalle)
    config.secciones[0].incluir = False
    vistas = pres.secciones_vista(config, detalle)
    contexto = pres.construir_contexto(detalle, config, vistas, {}, set(), {})
    assert [s["titulo"] for s in contexto["secciones"]] == ["MESA BANQUETE"]
    assert [f["titulo"] for f in contexto["concentrado"]] == ["SILLAS", "MESA BANQUETE"]


def test_prompt_de_montaje_lleva_piezas_brief_e_indicaciones():
    detalle = _detalle()
    config = pres.config_por_defecto(detalle)
    config.brief = "boda al atardecer, tonos chocolate"
    vistas = pres.secciones_vista(config, detalle)
    items = [i for i in detalle.items if i.categoria == "SILLAS"]
    prompt = pres.prompt_montaje(config, vistas[0], items, "que se vea la pérgola al fondo")
    assert "120 x SILLA TIFFANY BLANCA (INCLUYE MOÑO)" in prompt
    assert "boda al atardecer, tonos chocolate" in prompt
    assert "que se vea la pérgola al fondo" in prompt
    assert "sin logotipos" in prompt


def test_paleta_oscura_usa_identificadores_crema():
    detalle = _detalle()
    config = pres.config_por_defecto(detalle)
    config.paleta = Paleta(fondo="#101010", texto="#FFFFFF", acento="#C9A27E")
    vistas = pres.secciones_vista(config, detalle)
    contexto = pres.construir_contexto(detalle, config, vistas, {}, set(), {})
    assert contexto["monograma"] == pres.logo("monograma", pres.CREMA)
    assert contexto["logotipo_menta"] == pres.logo("logotipo", pres.MENTA)


def test_logo_solo_acepta_colores_de_marca():
    with pytest.raises(ValueError):
        pres.logo("monograma", "#FF0000")


def _foto(color=(210, 180, 140)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (900, 700), color).save(buffer, format="JPEG")
    return buffer.getvalue()


def test_pdf_editorial_se_genera_con_todas_sus_paginas(tmp_path):
    detalle = _detalle()
    config = pres.config_por_defecto(detalle)
    config.evento = "BODA ANA Y LUIS"
    vistas = pres.secciones_vista(config, detalle)
    foto = pres.foto_a_data_uri(_foto(), 800)
    fotos_huecos = {"portada": foto, "manifiesto": foto, "cierre": foto, "montaje:SILLAS": foto}
    ids_con_foto = [str(i.imagen_id) for i in detalle.items if i.imagen_id]
    contexto = pres.construir_contexto(detalle, config, vistas, fotos_huecos, {"montaje:SILLAS"}, {ids_con_foto[0]: foto})
    pdf = pres.html_a_pdf(pres.renderizar_html(contexto))
    assert pdf.startswith(b"%PDF")

    import pypdfium2 as pdfium

    documento = pdfium.PdfDocument(pdf)
    # portada, manifiesto, (apertura + piezas) por cada una de las 2 secciones, cierre, concentrado y monograma
    assert len(documento) == 9
    ancho, alto = documento[0].get_size()
    assert (round(ancho), round(alto)) == (pres.ANCHO_PAGINA, pres.ALTO_PAGINA)
    texto = "\n".join(pagina.get_textpage().get_text_range() for pagina in documento)
    assert "BODA ANA Y LUIS" in texto
    assert "RENDER CONCEPTUAL" in texto  # etiqueta (en mayúsculas) del montaje generado con IA
    assert "Subtotal mobiliario" in texto and "Total" in texto
