// Tipos que espejan los esquemas Pydantic del backend (backend/app/db/modelos.py).

export type Rol = 'vendedor' | 'admin'
export type TipoImagen = 'oficial' | 'variante' | 'generada'
export type TipoItem = 'catalogo' | 'ad_hoc'
export type EstadoCotizacion = 'revision' | 'generada'
export type EstadoItem = 'falta_imagen' | 'sugerida' | 'variante' | 'render_conceptual'

export interface CatalogoItem {
  id: string
  codigo: string
  nombre: string
  categoria: string
  activo: boolean
}

export interface Imagen {
  id: string
  item_id: string | null
  ruta_storage: string
  tipo: TipoImagen
  etiquetas: string[]
  origen: Record<string, unknown>
  subida_por: string | null
  usos: number
  creado_en: string | null
  url: string | null
}

export interface CotizacionItem {
  id: string
  cotizacion_id: string
  item_id: string | null
  codigo_origen: string
  descripcion_origen: string
  cantidad: number
  precio_unitario: number
  imagen_id: string | null
  tipo_item: TipoItem
  es_render_conceptual: boolean
  orden: number
  imagen: Imagen | null
  item: CatalogoItem | null
  estado: EstadoItem
  importe: number
}

export interface CotizacionResumen {
  id: string
  nombre_cliente: string
  referencia_externa: string
  creado_por: string
  archivo_origen_ruta: string
  estado: EstadoCotizacion
  creado_en: string
  actualizado_en: string
  total_items: number
  items_pendientes: number
}

export interface CotizacionDetalle extends CotizacionResumen {
  items: CotizacionItem[]
  total: number
}

export interface ResultadoPdf {
  url: string
  ruta_storage: string
}

export interface ResultadoGeneracion {
  imagenes: Imagen[]
}

export interface ItemSinImagen {
  id: string
  codigo: string
  nombre: string
  categoria: string
  veces_cotizado: number
}

export interface ResumenBiblioteca {
  items_activos: number
  items_con_oficial: number
  porcentaje_con_oficial: number
  total_variantes: number
  total_generadas: number
  total_sin_imagen: number
  items_sin_imagen: ItemSinImagen[]
}
