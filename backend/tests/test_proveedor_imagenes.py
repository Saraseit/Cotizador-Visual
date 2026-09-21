from io import BytesIO

import pytest
from PIL import Image

from app.servicios.proveedor_imagenes import (
    ErrorProveedorImagenes,
    ProveedorSimulado,
    construir_prompt,
    preparar_imagen_base,
)


def _jpg(ancho: int, alto: int) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (ancho, alto), (180, 120, 90)).save(buffer, format="JPEG", quality=80)
    return buffer.getvalue()


def test_preparar_imagen_base_convierte_jpg_grande_a_png_rgba_de_1024():
    salida = preparar_imagen_base(_jpg(2400, 1600))
    assert salida[:8] == b"\x89PNG\r\n\x1a\n"
    imagen = Image.open(BytesIO(salida))
    assert imagen.format == "PNG"
    assert imagen.mode == "RGBA"
    assert max(imagen.size) == 1024
    assert imagen.size == (1024, 683)  # conserva la proporción


def test_preparar_imagen_base_no_agranda_imagenes_pequenas():
    imagen = Image.open(BytesIO(preparar_imagen_base(_jpg(300, 200))))
    assert imagen.size == (300, 200)


def test_preparar_imagen_base_rechaza_bytes_invalidos():
    with pytest.raises(ErrorProveedorImagenes, match="no es válida"):
        preparar_imagen_base(b"esto no es una imagen")


async def test_proveedor_simulado_devuelve_png_normalizados():
    salidas = await ProveedorSimulado().generar_variantes(_jpg(1500, 1500), "nogal", 4)
    assert len(salidas) == 4
    for datos in salidas:
        imagen = Image.open(BytesIO(datos))
        assert imagen.format == "PNG"
        assert max(imagen.size) <= 1024


def test_prompt_concatena_estilo_y_peticion():
    prompt = construir_prompt("  Estilo fijo. ", " madera nogal ")
    assert prompt.startswith("Estilo fijo.")
    assert prompt.endswith("Cambio solicitado por el cliente: madera nogal")


def test_input_fidelity_solo_para_la_familia_gpt_image_1():
    from app.servicios.proveedor_imagenes import acepta_input_fidelity

    assert acepta_input_fidelity("gpt-image-1")
    assert acepta_input_fidelity("gpt-image-1.5")
    assert acepta_input_fidelity("gpt-image-1-mini")
    assert not acepta_input_fidelity("gpt-image-2.5-sunburst")
    assert not acepta_input_fidelity("gpt-image-2.5-flare")
    assert not acepta_input_fidelity("gpt-image-2")


async def test_openai_no_manda_input_fidelity_con_el_modelo_nuevo():
    from types import SimpleNamespace

    from app.servicios.proveedor_imagenes import ProveedorOpenAI

    llamadas: list[dict] = []

    class ImagenesFalsas:
        async def edit(self, **kwargs):
            llamadas.append(kwargs)
            return SimpleNamespace(data=[SimpleNamespace(b64_json="aGk=")] * kwargs["n"])

    for modelo, debe_mandarla in (("gpt-image-2.5-sunburst", False), ("gpt-image-1", True)):
        proveedor = ProveedorOpenAI(api_key="sk-prueba", modelo=modelo, prompt_estilo="estilo")
        proveedor._cliente = SimpleNamespace(images=ImagenesFalsas())
        salidas = await proveedor.generar_variantes(_jpg(400, 300), "nogal", 4)
        assert len(salidas) == 4
        assert ("input_fidelity" in llamadas[-1]) is debe_mandarla, modelo
        assert llamadas[-1]["model"] == modelo and llamadas[-1]["n"] == 4
