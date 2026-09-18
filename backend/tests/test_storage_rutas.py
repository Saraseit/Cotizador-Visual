from app.servicios.storage import nombre_seguro, ruta_imagen_catalogo


def test_nombre_seguro_quita_espacios_y_caracteres_raros():
    assert nombre_seguro(" Silla Ñandú #1.png ") == "Silla_and_1.png"
    assert nombre_seguro("", "archivo") == "archivo"
    assert nombre_seguro("///", "x") == "x"


def test_ruta_catalogo_misma_carpeta_para_endpoint_y_seeding():
    # El seeding sube "<codigo>.png"; el endpoint sube "<uuid>.png": deben caer en la misma carpeta.
    seeding = ruta_imagen_catalogo("SIL 001/Ñ", "SIL-001.png")
    endpoint = ruta_imagen_catalogo("SIL 001/Ñ", "abc123.png")
    assert seeding.rsplit("/", 1)[0] == endpoint.rsplit("/", 1)[0] == "catalogo/SIL_001"
    assert "/" not in seeding.rsplit("/", 1)[1]


def test_ruta_catalogo_generadas_y_ad_hoc():
    assert ruta_imagen_catalogo("MES-002", "x.png", "generadas") == "catalogo/MES-002/generadas/x.png"
    assert ruta_imagen_catalogo(None, "x.png") == "ad_hoc/x.png"
    assert ruta_imagen_catalogo(None, "x.png", "generadas") == "ad_hoc/generadas/x.png"
