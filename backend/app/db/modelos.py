"""Esquemas Pydantic que expone la API.

Reflejan las tablas de Supabase (ver `supabase/migrations/`) más campos calculados
(URL firmada de la imagen, estado del ítem, importes).
"""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

Rol = Literal["vendedor", "admin"]
TipoImagen = Literal["oficial", "variante", "generada"]
TipoItem = Literal["catalogo", "ad_hoc"]
EstadoCotizacion = Literal["revision", "generada"]
EstadoItem = Literal["falta_imagen", "sugerida", "variante", "render_conceptual"]
Cargo = Literal["flete", "montaje"]


# ---------------------------------------------------------------------------
# Perfiles y usuarios
# ---------------------------------------------------------------------------

class Perfil(BaseModel):
    id: UUID
    nombre: str = ""
    rol: Rol = "vendedor"


class PerfilYo(Perfil):
    email: str | None = None


class UsuarioAdmin(BaseModel):
    """Vista de administración: combina Supabase Auth con la tabla perfiles."""

    id: UUID
    email: str | None = None
    nombre: str = ""
    rol: Rol = "vendedor"
    creado_en: datetime | None = None
    ultimo_acceso: datetime | None = None


class UsuarioEntrada(BaseModel):
    email: str = Field(min_length=5, max_length=120)
    contrasena: str = Field(min_length=8, max_length=72)
    nombre: str = Field(default="", max_length=80)
    rol: Rol = "vendedor"


class UsuarioActualizacion(BaseModel):
    nombre: str | None = Field(default=None, max_length=80)
    rol: Rol | None = None
    contrasena: str | None = Field(default=None, min_length=8, max_length=72)


# ---------------------------------------------------------------------------
# Imágenes
# ---------------------------------------------------------------------------

class Imagen(BaseModel):
    id: UUID
    item_id: UUID | None = None
    ruta_storage: str
    tipo: TipoImagen
    etiquetas: list[str] = Field(default_factory=list)
    origen: dict[str, Any] = Field(default_factory=dict)
    subida_por: UUID | None = None
    usos: int = 0
    creado_en: datetime | None = None
    # URL firmada de corta duración, calculada por el backend.
    url: str | None = None


class PeticionGenerarImagen(BaseModel):
    """`item_id` es opcional: para ítems ad hoc se genera a partir de cualquier imagen base."""

    imagen_base_id: UUID
    peticion: str = Field(min_length=3, max_length=600)
    item_id: UUID | None = None
    # Sólo informativo, para el registro de generaciones.
    cotizacion_id: UUID | None = None


class ResultadoGeneracion(BaseModel):
    imagenes: list[Imagen]


# ---------------------------------------------------------------------------
# Catálogo y listas de precios
# ---------------------------------------------------------------------------

class ListaPrecios(BaseModel):
    id: UUID
    nombre: str
    orden: int = 0
    activo: bool = True


class ListaPreciosEntrada(BaseModel):
    nombre: str = Field(min_length=1, max_length=60)
    orden: int | None = None
    activo: bool | None = None


class PrecioItem(BaseModel):
    lista_id: UUID
    precio: float = 0
    nombre_lista: str | None = None


class CatalogoItem(BaseModel):
    id: UUID
    codigo: str
    nombre: str
    categoria: str = ""
    activo: bool = True
    descripcion: str = ""
    medidas: str = ""
    etiquetas: list[str] = Field(default_factory=list)
    costo_reposicion: float | None = None
    # Calculados
    precios: list[PrecioItem] = Field(default_factory=list)
    imagen_oficial: Imagen | None = None
    total_imagenes: int = 0


class CatalogoItemEntrada(BaseModel):
    codigo: str = Field(min_length=1, max_length=40)
    nombre: str = Field(min_length=1, max_length=160)
    categoria: str = Field(default="", max_length=80)
    descripcion: str = Field(default="", max_length=2000)
    medidas: str = Field(default="", max_length=200)
    etiquetas: list[str] = Field(default_factory=list)
    costo_reposicion: float | None = Field(default=None, ge=0)
    activo: bool = True
    # lista_id -> precio. Las listas que no aparezcan quedan sin precio.
    precios: dict[UUID, float] = Field(default_factory=dict)


class CatalogoItemActualizacion(BaseModel):
    codigo: str | None = Field(default=None, min_length=1, max_length=40)
    nombre: str | None = Field(default=None, min_length=1, max_length=160)
    categoria: str | None = Field(default=None, max_length=80)
    descripcion: str | None = Field(default=None, max_length=2000)
    medidas: str | None = Field(default=None, max_length=200)
    etiquetas: list[str] | None = None
    costo_reposicion: float | None = Field(default=None, ge=0)
    activo: bool | None = None
    precios: dict[UUID, float] | None = None


class CargaTexto(BaseModel):
    """Alta rápida: una línea por ítem `codigo; nombre; categoria; descripcion; medidas; costo; etiqueta|etiqueta`."""

    texto: str = Field(min_length=1, max_length=200_000)


class ResultadoCargaTexto(BaseModel):
    creados: int = 0
    actualizados: int = 0
    errores: list[str] = Field(default_factory=list)
    items: list[CatalogoItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Cotizaciones
# ---------------------------------------------------------------------------

class CotizacionItem(BaseModel):
    id: UUID
    cotizacion_id: UUID
    item_id: UUID | None = None
    codigo_origen: str = ""
    descripcion_origen: str = ""
    cantidad: float = 1
    precio_unitario: float = 0
    imagen_id: UUID | None = None
    tipo_item: TipoItem
    es_render_conceptual: bool = False
    orden: int = 0
    # Sección del PDF del sistema ('' si no tiene) y, si no es mobiliario, el tipo de cargo.
    categoria: str = ""
    cargo: Cargo | None = None
    # Campos calculados
    imagen: Imagen | None = None
    item: CatalogoItem | None = None
    estado: EstadoItem = "falta_imagen"
    importe: float = 0


class CotizacionResumen(BaseModel):
    id: UUID
    nombre_cliente: str = ""
    referencia_externa: str = ""
    creado_por: UUID
    archivo_origen_ruta: str = ""
    estado: EstadoCotizacion = "revision"
    creado_en: datetime
    actualizado_en: datetime
    total_items: int = 0
    items_pendientes: int = 0


class CotizacionDetalle(CotizacionResumen):
    items: list[CotizacionItem] = Field(default_factory=list)
    # Totales: subtotal de las partidas de mobiliario, cargos, IVA del PDF (None = "más IVA") y total.
    subtotal: float = 0
    flete: float = 0
    montaje: float = 0
    iva: float | None = None
    total: float = 0
    # Sólo al crear: cuántas fotos nuevas del PDF se guardaron en la biblioteca.
    fotos_importadas: int = 0


class Reordenar(BaseModel):
    """Ids de las partidas en el nuevo orden. Las que no vengan conservan su orden y van al final."""

    ids: list[UUID] = Field(min_length=1)


class AsignarCargo(BaseModel):
    """`null` devuelve la partida a mobiliario normal."""

    cargo: Cargo | None = None


class AsignarImagen(BaseModel):
    """Cuerpo de PATCH /cotizaciones/{id}/items/{item_id}. `null` quita la imagen."""

    imagen_id: UUID | None = None


class ResultadoPdf(BaseModel):
    url: str
    ruta_storage: str


# ---------------------------------------------------------------------------
# Biblioteca
# ---------------------------------------------------------------------------

class ItemSinImagen(BaseModel):
    id: UUID
    codigo: str
    nombre: str
    categoria: str = ""
    veces_cotizado: int = 0


class ResumenBiblioteca(BaseModel):
    items_activos: int = 0
    items_con_oficial: int = 0
    porcentaje_con_oficial: float = 0
    total_variantes: int = 0
    total_generadas: int = 0
    total_generaciones_24h: int = 0
    total_sin_imagen: int = 0
    items_sin_imagen: list[ItemSinImagen] = Field(default_factory=list)


def calcular_estado_item(imagen: dict[str, Any] | Imagen | None) -> EstadoItem:
    """Estado que ve el vendedor en la tabla de revisión, derivado de la imagen asignada."""
    if imagen is None:
        return "falta_imagen"
    tipo = imagen.tipo if isinstance(imagen, Imagen) else imagen.get("tipo")
    if tipo == "oficial":
        return "sugerida"
    if tipo == "generada":
        return "render_conceptual"
    return "variante"
