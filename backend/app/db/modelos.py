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


class Perfil(BaseModel):
    id: UUID
    nombre: str = ""
    rol: Rol = "vendedor"


class CatalogoItem(BaseModel):
    id: UUID
    codigo: str
    nombre: str
    categoria: str = ""
    activo: bool = True


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
    total: float = 0


class AsignarImagen(BaseModel):
    """Cuerpo de PATCH /cotizaciones/{id}/items/{item_id}. `null` quita la imagen."""

    imagen_id: UUID | None = None


class PeticionGenerarImagen(BaseModel):
    item_id: UUID
    imagen_base_id: UUID
    peticion: str = Field(min_length=3, max_length=600)


class ResultadoGeneracion(BaseModel):
    imagenes: list[Imagen]


class ResultadoPdf(BaseModel):
    url: str
    ruta_storage: str


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
