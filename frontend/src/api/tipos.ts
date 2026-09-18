// Tipos que espejan los esquemas Pydantic del backend (backend/app/db/modelos.py).

export type Rol = 'vendedor' | 'admin'
export type TipoImagen = 'oficial' | 'variante' | 'generada'
export type TipoItem = 'catalogo' | 'ad_hoc'
export type EstadoCotizacion = 'revision' | 'generada'
export type EstadoItem = 'falta_imagen' | 'sugerida' | 'variante' | 'render_conceptual'

// --- Salud ------------------------------------------------------------------

export interface Verificacion {
  ok: boolean
  detalle: string
}

export interface Salud {
  estado: 'ok' | 'degradado' | 'caido'
  entorno: string
  version: string
  proveedor_imagenes: string
  verificaciones: Record<string, Verificacion>
}

// --- Perfil y usuarios ------------------------------------------------------

export interface PerfilYo {
  id: string
  nombre: string
  rol: Rol
  email: string | null
}

export interface UsuarioAdmin {
  id: string
  email: string | null
  nombre: string
  rol: Rol
  creado_en: string | null
  ultimo_acceso: string | null
}

export interface UsuarioEntrada {
  email: string
  contrasena: string
  nombre: string
  rol: Rol
}

export interface UsuarioActualizacion {
  nombre?: string
  rol?: Rol
  contrasena?: string
}

// --- Imágenes ---------------------------------------------------------------

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

export interface ResultadoGeneracion {
  imagenes: Imagen[]
}

// --- Catálogo ---------------------------------------------------------------

export interface ListaPrecios {
  id: string
  nombre: string
  orden: number
  activo: boolean
}

export interface PrecioItem {
  lista_id: string
  precio: number
  nombre_lista: string | null
}

export interface CatalogoItem {
  id: string
  codigo: string
  nombre: string
  categoria: string
  activo: boolean
  descripcion: string
  medidas: string
  etiquetas: string[]
  costo_reposicion: number | null
  precios: PrecioItem[]
  imagen_oficial: Imagen | null
  total_imagenes: number
}

export interface CatalogoItemEntrada {
  codigo: string
  nombre: string
  categoria: string
  descripcion: string
  medidas: string
  etiquetas: string[]
  costo_reposicion: number | null
  activo: boolean
  // lista_id -> precio
  precios: Record<string, number>
}

export type CatalogoItemActualizacion = Partial<CatalogoItemEntrada>

export interface ResultadoCargaTexto {
  creados: number
  actualizados: number
  errores: string[]
  items: CatalogoItem[]
}

// --- Cotizaciones -----------------------------------------------------------

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

// --- Biblioteca -------------------------------------------------------------

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
  total_generaciones_24h: number
  total_sin_imagen: number
  items_sin_imagen: ItemSinImagen[]
}
