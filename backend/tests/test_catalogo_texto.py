from app.servicios.catalogo_texto import detectar_separador, parsear_texto_catalogo


def test_detecta_separador_por_prioridad():
    assert detectar_separador("a\tb;c") == "\t"
    assert detectar_separador("a;b,c") == ";"
    assert detectar_separador("a|b,c") == "|"
    assert detectar_separador("a,b") == ","
    assert detectar_separador("solo") == ","


def test_parsea_lineas_completas_con_punto_y_coma():
    texto = (
        "codigo; nombre; categoria; descripcion; medidas; costo; etiquetas\n"
        "sil-010; Silla Luis XV; Sillas; Silla clásica tapizada; 45 x 50 x 95 cm; $1,250.00; boda|clásico\n"
        "\n"
        "MES-010; Mesa rústica; Mesas\n"
    )
    filas, errores = parsear_texto_catalogo(texto)
    assert errores == []
    assert [f["codigo"] for f in filas] == ["SIL-010", "MES-010"]
    silla = filas[0]
    assert silla["nombre"] == "Silla Luis XV"
    assert silla["categoria"] == "Sillas"
    assert silla["descripcion"] == "Silla clásica tapizada"
    assert silla["medidas"] == "45 x 50 x 95 cm"
    assert silla["costo_reposicion"] == 1250.0
    assert silla["etiquetas"] == ["boda", "clásico"]
    mesa = filas[1]
    assert mesa["descripcion"] == "" and "costo_reposicion" not in mesa


def test_lineas_sin_codigo_y_costos_invalidos_generan_errores():
    filas, errores = parsear_texto_catalogo("; Sin código; X\nABC-1; Cosa; Cat; ; ; muchos\n")
    assert [f["codigo"] for f in filas] == ["ABC-1"]
    assert len(errores) == 2
    assert "Línea 1" in errores[0] and "Línea 2" in errores[1]


def test_codigo_repetido_se_queda_con_la_ultima_linea():
    filas, _ = parsear_texto_catalogo("A-1, Primero\nA-1, Segundo")
    assert len(filas) == 1 and filas[0]["nombre"] == "Segundo"


def test_solo_codigo_usa_el_codigo_como_nombre():
    filas, _ = parsear_texto_catalogo("ZZ-9")
    assert filas[0]["nombre"] == "ZZ-9"
