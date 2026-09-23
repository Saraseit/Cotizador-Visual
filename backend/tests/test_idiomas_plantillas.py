"""Idioma, moneda, plantillas y paletas: lo que cambia la presentación sin tocar la marca."""

from io import BytesIO
from uuid import uuid4

import pytest
from PIL import Image
from pydantic import ValidationError

from app.db.modelos import (
    ConfigPresentacion,
    ConfigPresentacionEntrada,
    CotizacionDetalle,
    CotizacionItem,
    Paleta,
    ParametrosPlantilla,
    descripcion_impresa,
)
from app.routers.plantillas import _parametros_desde_ia
from app.servicios import idiomas
from app.servicios import presentacion as pres


# --- Moneda ------------------------------------------------------------------

def test_dinero_en_pesos_y_en_dolares():
    assert idiomas.Dinero()(1850) == "$1,850.00"
    assert idiomas.Dinero("USD", 18.5)(1850) == "US$100.00"
    # Sin tipo de cambio no se inventa la conversión: se queda en pesos.
    assert idiomas.Dinero("USD", None)(1850) == "$1,850.00"


def test_dolares_exige_tipo_de_cambio():
    with pytest.raises(ValidationError):
        ConfigPresentacionEntrada(moneda="USD")
    assert ConfigPresentacionEntrada(moneda="USD", tipo_cambio=18.5).tipo_cambio == 18.5


# --- Medidas e idioma --------------------------------------------------------

@pytest.mark.parametrize(
    "original, esperado",
    [
        ("MESA REDONDA DE 1.80 DIAMETRO", "MESA REDONDA DE 5'11\" DIAMETRO"),
        ("MESA MITO 270 X 120 CM", "MESA MITO 8'10\" x 3'11\""),
        ("TARIMA 6 X 4 M CON FALDÓN", "TARIMA 19'8\" x 13'1\" CON FALDÓN"),
        ("SILLA THONET", "SILLA THONET"),  # sin medidas no cambia nada
    ],
)
def test_medidas_a_pies_y_pulgadas(original, esperado):
    assert idiomas.convertir_medidas(original) == esperado


def test_medidas_del_catalogo_traducen_etiqueta_y_unidad():
    assert idiomas.traducir_medidas("ancho 190 cm · alto 75 cm", "en") == "width 6'3\" · height 2'6\""
    # En español no se toca.
    assert idiomas.traducir_medidas("ancho 190 cm", "es") == "ancho 190 cm"


def test_etiquetas_caen_a_español_si_falta_la_traduccion():
    assert idiomas.etiqueta("en", "flete") == "Freight"
    assert idiomas.etiqueta("pt", "flete") == "Flete"  # idioma desconocido
    assert idiomas.etiqueta("en", "clave_que_no_existe") == "clave_que_no_existe"


def test_traductor_prefiere_la_cache_y_si_no_usa_el_glosario():
    traductor = idiomas.Traductor("en", {"SILLA TIFFANY BLANCA": "WHITE TIFFANY CHAIR"})
    assert traductor("SILLA TIFFANY BLANCA") == "WHITE TIFFANY CHAIR"
    # Sin caché, el glosario deja el texto legible y convierte las medidas.
    assert traductor("MESA DE 1.80") == "TABLE OF 5'11\""
    assert idiomas.Traductor("es")("SILLA TIFFANY BLANCA") == "SILLA TIFFANY BLANCA"


# --- Descripción editada -----------------------------------------------------

def _item(descripcion="SILLA TIFFANY BLANCA", editada="", categoria="SILLAS", cantidad=10, precio=45):
    return CotizacionItem(
        id=uuid4(),
        cotizacion_id=uuid4(),
        descripcion_origen=descripcion,
        descripcion_editada=editada,
        cantidad=cantidad,
        precio_unitario=precio,
        tipo_item="catalogo",
        orden=0,
        categoria=categoria,
        importe=cantidad * precio,
    )


def _detalle(items):
    subtotal = round(sum(i.importe for i in items if not i.cargo), 2)
    return CotizacionDetalle(
        id=uuid4(),
        nombre_cliente="CLIENTE",
        referencia_externa="1",
        creado_por=uuid4(),
        archivo_origen_ruta="x",
        estado="revision",
        creado_en="2026-09-23T10:00:00Z",
        actualizado_en="2026-09-23T10:00:00Z",
        items=items,
        subtotal=subtotal,
        total=subtotal,
        total_items=len(items),
    )


def test_la_descripcion_editada_manda_sobre_la_del_sistema():
    assert descripcion_impresa(_item(editada="SILLA TIFFANY (CON MOÑO)")) == "SILLA TIFFANY (CON MOÑO)"
    assert descripcion_impresa(_item(editada="   ")) == "SILLA TIFFANY BLANCA"


def test_lo_editado_no_se_manda_a_traducir_ni_se_convierte():
    detalle = _detalle([_item(), _item(descripcion="MESA DE 1.80", editada="ROUND TABLE 6 FT")])
    config = pres.config_por_defecto(detalle)
    config.idioma = "en"
    vistas = pres.secciones_vista(config, detalle)

    textos = pres.textos_traducibles(detalle, config, vistas)
    assert "SILLA TIFFANY BLANCA" in textos
    assert "MESA DE 1.80" not in textos  # la corrigió el vendedor

    contexto = pres.construir_contexto(detalle, config, vistas, {}, set(), {})
    nombres = [p.nombre for pagina in contexto["secciones"][0]["paginas"] for p in pagina["piezas"]]
    assert "ROUND TABLE 6 FT" in nombres  # tal cual, sin pasar por el glosario


# --- Plantillas y paletas ----------------------------------------------------

def test_parametros_de_la_ia_se_filtran_a_lo_que_el_modelo_acepta():
    parametros, nombre, descripcion = _parametros_desde_ia(
        {
            "composicion": "revista",
            "piezas_por_pagina": 4,
            "escala_titulos": 1.2,
            "paleta": {"fondo": "#101010", "texto": "#FFFFFF", "acento": "#C9A27E"},
            "nombre": "Editorial nocturno",
            "descripcion": "Fotos a toda página y títulos grandes.",
            "inventado": "lo que sea",
        }
    )
    assert (parametros.composicion, parametros.piezas_por_pagina, parametros.escala_titulos) == ("revista", 4, 1.2)
    assert parametros.paleta.fondo == "#101010"
    assert (nombre, descripcion) == ("Editorial nocturno", "Fotos a toda página y títulos grandes.")


def test_parametros_fuera_de_rango_caen_a_los_de_por_defecto():
    parametros, _, _ = _parametros_desde_ia({"composicion": "collage", "escala_titulos": 9})
    assert parametros == ParametrosPlantilla()


def _imagen(color) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (400, 300), color).save(buffer, format="JPEG")
    return buffer.getvalue()


def test_paleta_de_imagen_clara_y_oscura():
    clara = pres.paleta_de_imagen(_imagen((214, 186, 150)))
    assert not pres.es_oscuro(clara.fondo) and pres.es_oscuro(clara.texto)
    oscura = pres.paleta_de_imagen(_imagen((28, 30, 38)))
    assert pres.es_oscuro(oscura.fondo) and not pres.es_oscuro(oscura.texto)
    for paleta in (clara, oscura):  # colores válidos para el PDF
        Paleta.model_validate(paleta.model_dump())


def test_hay_paletas_predefinidas_con_contraste():
    predefinidas = pres.paletas_predefinidas()
    assert len(predefinidas) >= 10
    assert all(p.predefinida and p.id is None for p in predefinidas)
    for guardada in predefinidas:
        claro, oscuro = sorted((guardada.paleta.fondo, guardada.paleta.texto), key=pres.luminancia)
        assert pres.luminancia(oscuro) - pres.luminancia(claro) > 0.45, guardada.nombre


# --- Composiciones -----------------------------------------------------------

def _html(composicion: str, piezas_por_pagina: int = 2) -> str:
    items = [_item(descripcion=f"PIEZA {i}") for i in range(6)]
    detalle = _detalle(items)
    config = pres.config_por_defecto(detalle)
    config.parametros.composicion = composicion
    config.parametros.piezas_por_pagina = piezas_por_pagina
    vistas = pres.secciones_vista(config, detalle)
    return pres.renderizar_html(pres.construir_contexto(detalle, config, vistas, {"portada": "data:,x"}, set(), {}))


def test_cada_composicion_arma_una_portada_distinta():
    editorial, revista, catalogo = (_html(c) for c in ("editorial", "revista", "catalogo"))
    # Se buscan las clases usadas en el cuerpo, no las reglas del CSS (que están siempre).
    assert '"velo-bajo"' in revista and '"velo-bajo"' not in editorial  # foto a toda página con degradado
    assert 'class="banda"' in catalogo and 'class="banda"' not in revista  # banda de color con el título
    assert editorial != revista != catalogo


@pytest.mark.parametrize("por_pagina, clase, paginas", [(1, "solo", 6), (2, "par", 3), (4, "rejilla", 2), (6, "rejilla densa", 1)])
def test_piezas_por_pagina_reparte_y_marca_el_formato(por_pagina, clase, paginas):
    html = _html("editorial", por_pagina)
    assert html.count(f'class="pagina {clase}"') == paginas


def test_la_plantilla_puede_quitar_manifiesto_y_cierre():
    items = [_item()]
    detalle = _detalle(items)
    config = pres.config_por_defecto(detalle)
    config.parametros.mostrar_manifiesto = False
    config.parametros.mostrar_cierre = False
    vistas = pres.secciones_vista(config, detalle)
    fotos = {"portada": "data:,x", "manifiesto": "data:,x", "cierre": "data:,x"}
    html = pres.renderizar_html(pres.construir_contexto(detalle, config, vistas, fotos, set(), {}))
    assert config.manifiesto[0].split("\n")[0] not in html


def test_config_vieja_con_paleta_suelta_se_migra_a_parametros():
    detalle = _detalle([_item()])
    config = pres.leer_config(
        {"titulo": "PROPUESTA", "tipografia_titulos": "bebas", "paleta": {"fondo": "#101010", "texto": "#FFFFFF", "acento": "#C9A27E"}},
        detalle,
    )
    assert config.parametros.tipografia_titulos == "bebas"
    assert config.parametros.paleta.fondo == "#101010"
    assert config.titulo == "PROPUESTA"


def test_la_nota_de_moneda_dice_el_tipo_de_cambio():
    detalle = _detalle([_item()])
    config = ConfigPresentacion(moneda="USD", tipo_cambio=18.5, idioma="en")
    vistas = pres.secciones_vista(config, detalle)
    contexto = pres.construir_contexto(detalle, config, vistas, {}, set(), {})
    assert "18.50 pesos per dollar" in contexto["nota_moneda"]
    assert contexto["total"].startswith("US$")
    assert contexto["totales"][0][0] == "Furniture subtotal"
