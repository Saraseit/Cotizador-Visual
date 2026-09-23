"""Configuración del backend leída desde variables de entorno.

Todas las variables están documentadas en `.env.example` en la raíz del repo.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ_BACKEND = Path(__file__).resolve().parent.parent

PROMPT_ESTILO_POR_DEFECTO = (
    "Edita la imagen de esta pieza de mobiliario conservando exactamente su forma, "
    "proporciones, estructura y dimensiones. Cambia únicamente el acabado, material o color "
    "que se describe a continuación; no agregues ni quites elementos. Muestra la pieza en "
    "ángulo de tres cuartos, sobre un fondo neutro claro y uniforme, con iluminación natural "
    "lateral suave. Sin texto, sin marcas de agua, sin logotipos y sin personas. Estilo de "
    "fotografía de producto limpia y realista."
)


class Configuracion(BaseSettings):
    model_config = SettingsConfigDict(
        # Se busca .env en la raíz del repo y en backend/ para poder correr desde ambas rutas.
        env_file=(RAIZ_BACKEND.parent / ".env", RAIZ_BACKEND / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Supabase ---------------------------------------------------------
    supabase_url: str
    supabase_service_role_key: str
    # Solo necesario si el proyecto usa firmas HS256 (JWT secret heredado).
    supabase_jwt_secret: str | None = None
    # Para proyectos con llaves asimétricas (ES256/RS256). Si se omite se deriva de supabase_url.
    supabase_jwks_url: str | None = None

    bucket_imagenes: str = "imagenes"
    bucket_exports: str = "exports"
    url_firmada_segundos: int = 600

    # --- Generación de imágenes -------------------------------------------
    # 'openai' usa gpt-image-2.5-sunburst; 'simulado' devuelve variantes locales sin llamar a ningún
    # proveedor (útil para desarrollar sin gastar créditos).
    proveedor_imagenes: str = "openai"
    openai_api_key: str | None = None
    openai_modelo_imagenes: str = "gpt-image-2.5-sunburst"
    openai_calidad_imagenes: str = "medium"
    # Modelo de texto/visión (leer inspiraciones y traducir). Vacío: se elige solo preguntándole a la
    # cuenta qué modelos tiene, para no depender del nombre del modelo del año en curso.
    openai_modelo_texto: str = ""
    variantes_por_generacion: int = 4
    prompt_estilo_fijo: str = PROMPT_ESTILO_POR_DEFECTO
    # Topes de llamadas al proveedor en una ventana de 24 h (cada llamada cuenta 1, produzca las imágenes que produzca).
    limite_generaciones_diarias_usuario: int = 20
    limite_generaciones_diarias_global: int = 100

    # --- Servidor -----------------------------------------------------------
    # Orígenes permitidos para CORS, separados por coma. Vacío: en 'desarrollo' se aceptan
    # localhost:5173 y cualquier https://*.vercel.app; en 'produccion' es obligatorio.
    cors_origenes: str = ""
    mapeo_columnas_ruta: str = "fixtures/mapeo_columnas.json"
    entorno: str = "desarrollo"

    @property
    def lista_cors(self) -> list[str]:
        return [o.strip() for o in self.cors_origenes.split(",") if o.strip()]

    @property
    def es_produccion(self) -> bool:
        return self.entorno.strip().lower() in {"produccion", "producción", "production", "prod"}

    @property
    def proveedor_efectivo(self) -> str:
        """'openai' sólo si hay llave; sin llave el backend cae a 'simulado' en vez de fallar."""
        if self.proveedor_imagenes == "openai" and not (self.openai_api_key or "").strip():
            return "simulado"
        return self.proveedor_imagenes

    def origenes_cors(self) -> tuple[list[str], str | None]:
        """(lista de orígenes, regex opcional). Lanza RuntimeError si en producción falta la variable."""
        if self.lista_cors:
            return self.lista_cors, None
        if self.es_produccion:
            raise RuntimeError(
                "ENTORNO=produccion exige CORS_ORIGENES con el dominio del frontend "
                "(por ejemplo https://cotizador.vercel.app). Defínela en las variables de Railway."
            )
        return ["http://localhost:5173", "http://127.0.0.1:5173"], r"https://.*\.vercel\.app"

    @property
    def jwks_url(self) -> str:
        return self.supabase_jwks_url or f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"

    @property
    def ruta_mapeo_columnas(self) -> Path:
        ruta = Path(self.mapeo_columnas_ruta)
        return ruta if ruta.is_absolute() else RAIZ_BACKEND / ruta


@lru_cache
def obtener_configuracion() -> Configuracion:
    return Configuracion()  # type: ignore[call-arg]
