import pytest

from app.config import Configuracion


def _config(**valores) -> Configuracion:
    base = {"supabase_url": "https://x.supabase.co", "supabase_service_role_key": "clave"}
    return Configuracion(_env_file=None, **base, **valores)  # type: ignore[call-arg]


def test_sin_llave_de_openai_cae_a_simulado():
    assert _config(proveedor_imagenes="openai", openai_api_key=None).proveedor_efectivo == "simulado"
    assert _config(proveedor_imagenes="openai", openai_api_key="   ").proveedor_efectivo == "simulado"
    assert _config(proveedor_imagenes="openai", openai_api_key="sk-1").proveedor_efectivo == "openai"
    assert _config(proveedor_imagenes="simulado").proveedor_efectivo == "simulado"


def test_cors_por_defecto_en_desarrollo_acepta_local_y_vercel():
    origenes, regex = _config().origenes_cors()
    assert "http://localhost:5173" in origenes
    assert regex is not None and "vercel" in regex


def test_cors_explicito_se_respeta_tal_cual():
    origenes, regex = _config(cors_origenes="https://a.com, https://b.com").origenes_cors()
    assert origenes == ["https://a.com", "https://b.com"]
    assert regex is None


def test_produccion_sin_cors_falla_con_mensaje_claro():
    with pytest.raises(RuntimeError, match="CORS_ORIGENES"):
        _config(entorno="produccion").origenes_cors()
    origenes, _ = _config(entorno="produccion", cors_origenes="https://app.vercel.app").origenes_cors()
    assert origenes == ["https://app.vercel.app"]


def test_valores_por_defecto_sanos():
    config = _config()
    assert config.entorno == "desarrollo"
    assert config.limite_generaciones_diarias_usuario == 20
    assert config.limite_generaciones_diarias_global == 100
    assert config.bucket_imagenes == "imagenes" and config.bucket_exports == "exports"
