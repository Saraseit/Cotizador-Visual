// Tipos que espejan los esquemas Pydantic del backend (backend/app/db/modelos.py).

export type Rol = 'vendedor' | 'admin'
export type TipoImagen = 'oficial' | 'variante' | 'generada' | 'ambientacion' | 'montaje' | 'inspiracion'
export type TipografiaTitulos = 'everett' | 'bebas'
export type TipoItem = 'catalogo' | 'ad_hoc'
export type EstadoCotizacion = 'revision' | 'generada'
export type EstadoItem = 'falta_imagen' | 'sugerida' | 'variante' | 'render_conceptual'
export type Cargo = 'flete' | 'montaje'

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
  /** Sección del PDF del sistema ('' si no tiene). */
  categoria: string
  /** Si no es mobiliario: flete o montaje (se suman abajo, no se imprimen como partida). */
  cargo: Cargo | null
  /** Texto ajustado para esta cotización; vacío = se usa el del sistema. */
  descripcion_editada: string
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
  subtotal: number
  flete: number
  montaje: number
  /** IVA impreso en el PDF del sistema; null si el documento sólo dice "más IVA". */
  iva: number | null
  total: number
  /** Sólo en la respuesta de subir: fotos nuevas del PDF guardadas en la biblioteca. */
  fotos_importadas?: number
}

// --- Presentación editorial --------------------------------------------------

export type Composicion = 'editorial' | 'revista' | 'catalogo'
export type Moneda = 'MXN' | 'USD'
export type Idioma = 'es' | 'en'
export type PiezasPorPagina = 1 | 2 | 4 | 6

/** Colores de la presentación. Los de marca (logo, menta) no se configuran. */
export interface Paleta {
  fondo: string
  texto: string
  acento: string
}

export interface SeccionPresentacion {
  /** Categoría del PDF del sistema; '' si la partida no traía sección. */
  clave: string
  titulo: string
  texto: string
  incluir: boolean
}

/** Cómo se ve la presentación. Salen de la inspiración y el vendedor los ajusta. */
export interface ParametrosPlantilla {
  composicion: Composicion
  tipografia_titulos: TipografiaTitulos
  paleta: Paleta
  /** 1.0 = un título que llena el ancho; menos, títulos discretos. */
  escala_titulos: number
  fotos_a_sangre: boolean
  piezas_por_pagina: PiezasPorPagina
  mostrar_manifiesto: boolean
  mostrar_cierre: boolean
}

export interface Plantilla {
  id: string
  nombre: string
  descripcion: string
  parametros: ParametrosPlantilla
  inspiraciones: Imagen[]
  creado_en: string | null
}

export interface PaletaGuardada {
  /** Sin id es una de las que trae la app. */
  id: string | null
  nombre: string
  paleta: Paleta
  predefinida: boolean
}

export interface PaletaEntrada {
  nombre: string
  paleta: Paleta
}

export interface ConfigPresentacionEntrada {
  brief: string
  titulo: string
  evento: string
  /** De qué plantilla salieron los parámetros (sus inspiraciones guían a la IA en los montajes). */
  plantilla_id: string | null
  parametros: ParametrosPlantilla
  mostrar_precios: boolean
  moneda: Moneda
  /** Pesos por dólar. Obligatorio si la moneda es USD. */
  tipo_cambio: number | null
  idioma: Idioma
  manifiesto: string[]
  cierre: string[]
  secciones: SeccionPresentacion[]
}

export interface ConfigPresentacion extends ConfigPresentacionEntrada {
  /** hueco ('portada', 'manifiesto', 'cierre', 'montaje:<clave>') -> id de imagen */
  imagenes: Record<string, string>
  /** Traducciones ya pagadas: texto en español -> texto traducido. */
  traducciones: Record<string, string>
}

export interface SeccionVista extends SeccionPresentacion {
  categoria: string
  partidas: number
  piezas: number
  importe: number
  /** Partidas con foto: son las referencias que se mandan a la IA para el montaje. */
  con_imagen: number
}

export interface Presentacion {
  cotizacion_id: string
  config: ConfigPresentacion
  secciones: SeccionVista[]
  imagenes: Record<string, Imagen>
  guardada: boolean
}

export interface ResultadoPdf {
  url: string
  ruta_storage: string
}

export type TipoPdf = 'base' | 'editorial'

/** Un PDF ya generado (propuesta base o presentación editorial), para la pantalla Propuestas. */
export interface PdfGenerado {
  id: string
  tipo: TipoPdf
  creado_en: string
  /** Para ver/imprimir desde el visor del navegador. Falta si el archivo ya no está en Storage. */
  url: string | null
  /** Fuerza la descarga en vez de abrir el visor. */
  url_descarga: string | null
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
