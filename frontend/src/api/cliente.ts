import { supabase } from '@/lib/supabase'

import type {
  Cargo,
  CatalogoItem,
  ConfigPresentacionEntrada,
  CatalogoItemActualizacion,
  FormatoPropuesta,
  CatalogoItemEntrada,
  CotizacionDetalle,
  CotizacionResumen,
  Imagen,
  ListaPrecios,
  PaletaEntrada,
  PaletaGuardada,
  ParametrosPlantilla,
  PdfGenerado,
  PerfilYo,
  Plantilla,
  Presentacion,
  ResultadoCargaTexto,
  ResultadoGeneracion,
  ResultadoPdf,
  ResumenBiblioteca,
  Salud,
  UsuarioActualizacion,
  UsuarioAdmin,
  UsuarioEntrada,
} from './tipos'

const BASE = ((import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000').replace(/\/$/, '')

export class ErrorApi extends Error {
  constructor(
    public estado: number,
    mensaje: string,
  ) {
    super(mensaje)
    this.name = 'ErrorApi'
  }
}

async function tokenActual(): Promise<string> {
  const { data } = await supabase.auth.getSession()
  if (!data.session) throw new ErrorApi(401, 'No hay sesión activa.')
  return data.session.access_token
}

async function peticion<T>(ruta: string, opciones: RequestInit = {}): Promise<T> {
  const encabezados = new Headers(opciones.headers)
  encabezados.set('Authorization', `Bearer ${await tokenActual()}`)
  if (opciones.body && !(opciones.body instanceof FormData)) {
    encabezados.set('Content-Type', 'application/json')
  }

  let respuesta: Response
  try {
    respuesta = await fetch(`${BASE}/api${ruta}`, { ...opciones, headers: encabezados })
  } catch {
    throw new ErrorApi(0, 'No se pudo conectar con el servidor.')
  }

  if (!respuesta.ok) {
    let detalle = respuesta.statusText || `Error ${respuesta.status}`
    try {
      const cuerpo = (await respuesta.json()) as { detail?: unknown }
      if (typeof cuerpo.detail === 'string') detalle = cuerpo.detail
      else if (cuerpo.detail) detalle = JSON.stringify(cuerpo.detail)
    } catch {
      // sin cuerpo JSON
    }
    throw new ErrorApi(respuesta.status, detalle)
  }
  if (respuesta.status === 204) return undefined as T
  return (await respuesta.json()) as T
}

const json = (cuerpo: unknown, method = 'POST'): RequestInit => ({ method, body: JSON.stringify(cuerpo) })

/** /api/salud no requiere sesión y responde 503 cuando Supabase no contesta; se lee el cuerpo igual. */
async function salud(): Promise<Salud> {
  let respuesta: Response
  try {
    respuesta = await fetch(`${BASE}/api/salud`)
  } catch {
    throw new ErrorApi(0, `No se pudo conectar con el backend en ${BASE}.`)
  }
  try {
    return (await respuesta.json()) as Salud
  } catch {
    throw new ErrorApi(respuesta.status, `El backend respondió ${respuesta.status} sin diagnóstico.`)
  }
}

export const api = {
  salud,
  perfil: {
    yo: () => peticion<PerfilYo>('/perfil/yo'),
  },
  cotizaciones: {
    listar: () => peticion<CotizacionResumen[]>('/cotizaciones'),
    obtener: (id: string) => peticion<CotizacionDetalle>(`/cotizaciones/${id}`),
    crear: (archivo: File) => {
      const datos = new FormData()
      datos.append('archivo', archivo)
      return peticion<CotizacionDetalle>('/cotizaciones', { method: 'POST', body: datos })
    },
    asignarImagen: (cotizacionId: string, itemId: string, imagenId: string | null) =>
      peticion<CotizacionDetalle>(`/cotizaciones/${cotizacionId}/items/${itemId}`, json({ imagen_id: imagenId }, 'PATCH')),
    generar: (id: string) => peticion<ResultadoPdf>(`/cotizaciones/${id}/generar`, { method: 'POST' }),
    reordenar: (cotizacionId: string, ids: string[]) =>
      peticion<CotizacionDetalle>(`/cotizaciones/${cotizacionId}/orden`, json({ ids }, 'PUT')),
    asignarCargo: (cotizacionId: string, itemId: string, cargo: Cargo | null) =>
      peticion<CotizacionDetalle>(`/cotizaciones/${cotizacionId}/items/${itemId}/cargo`, json({ cargo }, 'PUT')),
    pdfs: (cotizacionId: string) => peticion<PdfGenerado[]>(`/cotizaciones/${cotizacionId}/pdfs`),
    editarDescripcion: (cotizacionId: string, itemId: string, descripcion: string) =>
      peticion<CotizacionDetalle>(`/cotizaciones/${cotizacionId}/items/${itemId}/descripcion`, json({ descripcion }, 'PATCH')),
  },
  presentacion: {
    obtener: (cotizacionId: string) => peticion<Presentacion>(`/cotizaciones/${cotizacionId}/presentacion`),
    guardar: (cotizacionId: string, config: ConfigPresentacionEntrada) =>
      peticion<Presentacion>(`/cotizaciones/${cotizacionId}/presentacion`, json(config, 'PUT')),
    asignarImagen: (cotizacionId: string, hueco: string, imagenId: string | null) =>
      peticion<Presentacion>(`/cotizaciones/${cotizacionId}/presentacion/imagenes`, json({ hueco, imagen_id: imagenId }, 'PUT')),
    generarMontaje: (cotizacionId: string, clave: string, indicaciones = '') =>
      peticion<Presentacion>(`/cotizaciones/${cotizacionId}/presentacion/montajes`, json({ clave, indicaciones })),
    pdf: (cotizacionId: string) => peticion<ResultadoPdf>(`/cotizaciones/${cotizacionId}/presentacion/pdf`, { method: 'POST' }),
    traducir: (cotizacionId: string) => peticion<Presentacion>(`/cotizaciones/${cotizacionId}/presentacion/traducir`, { method: 'POST' }),
    formato: (cotizacionId: string, formato: FormatoPropuesta) =>
      peticion<Presentacion>(`/cotizaciones/${cotizacionId}/presentacion/formato`, json(formato, 'PUT')),
  },
  plantillas: {
    listar: () => peticion<Plantilla[]>('/plantillas'),
    crear: (archivo: File, nombre = '') => {
      const datos = new FormData()
      datos.append('archivo', archivo)
      if (nombre) datos.append('nombre', nombre)
      return peticion<Plantilla>('/plantillas', { method: 'POST', body: datos })
    },
    actualizar: (id: string, cambios: { nombre?: string; descripcion?: string; parametros?: ParametrosPlantilla }) =>
      peticion<Plantilla>(`/plantillas/${id}`, json(cambios, 'PATCH')),
    agregarInspiracion: (id: string, archivo: File) => {
      const datos = new FormData()
      datos.append('archivo', archivo)
      return peticion<Plantilla>(`/plantillas/${id}/inspiraciones`, { method: 'POST', body: datos })
    },
    quitarInspiracion: (id: string, imagenId: string) =>
      peticion<Plantilla>(`/plantillas/${id}/inspiraciones/${imagenId}`, { method: 'DELETE' }),
    analizar: (id: string) => peticion<Plantilla>(`/plantillas/${id}/analizar`, { method: 'POST' }),
    eliminar: (id: string) => peticion<void>(`/plantillas/${id}`, { method: 'DELETE' }),
  },
  paletas: {
    listar: () => peticion<PaletaGuardada[]>('/paletas'),
    crear: (entrada: PaletaEntrada) => peticion<PaletaGuardada>('/paletas', json(entrada)),
    actualizar: (id: string, entrada: PaletaEntrada) => peticion<PaletaGuardada>(`/paletas/${id}`, json(entrada, 'PATCH')),
    eliminar: (id: string) => peticion<void>(`/paletas/${id}`, { method: 'DELETE' }),
  },
  catalogo: {
    buscar: (termino: string, soloActivos = false) =>
      peticion<CatalogoItem[]>(`/catalogo/items?buscar=${encodeURIComponent(termino)}&solo_activos=${soloActivos}`),
    obtener: (id: string) => peticion<CatalogoItem>(`/catalogo/items/${id}`),
    crear: (entrada: CatalogoItemEntrada) => peticion<CatalogoItem>('/catalogo/items', json(entrada)),
    actualizar: (id: string, cambios: CatalogoItemActualizacion) => peticion<CatalogoItem>(`/catalogo/items/${id}`, json(cambios, 'PATCH')),
    cargarTexto: (texto: string) => peticion<ResultadoCargaTexto>('/catalogo/items/carga-texto', json({ texto })),
    imagenesDeItem: (itemId: string) => peticion<Imagen[]>(`/catalogo/items/${itemId}/imagenes`),
    listasPrecios: () => peticion<ListaPrecios[]>('/catalogo/listas-precios'),
    crearListaPrecios: (nombre: string) => peticion<ListaPrecios>('/catalogo/listas-precios', json({ nombre })),
    actualizarListaPrecios: (id: string, cambios: { nombre?: string; orden?: number; activo?: boolean }) =>
      peticion<ListaPrecios>(`/catalogo/listas-precios/${id}`, json(cambios, 'PATCH')),
  },
  imagenes: {
    ambientacion: () => peticion<Imagen[]>('/imagenes/ambientacion'),
    subir: (parametros: {
      archivo: File
      itemId?: string | null
      etiquetas?: string[]
      tipo?: 'oficial' | 'variante' | 'ambientacion'
    }) => {
      const datos = new FormData()
      datos.append('archivo', parametros.archivo)
      if (parametros.itemId) datos.append('item_id', parametros.itemId)
      if (parametros.etiquetas?.length) datos.append('etiquetas', parametros.etiquetas.join(','))
      if (parametros.tipo) datos.append('tipo', parametros.tipo)
      return peticion<Imagen>('/imagenes', { method: 'POST', body: datos })
    },
    generar: (cuerpo: { imagen_base_id: string; peticion: string; item_id?: string | null; cotizacion_id?: string | null }) =>
      peticion<ResultadoGeneracion>('/imagenes/generar', json(cuerpo)),
    eliminar: (id: string) => peticion<void>(`/imagenes/${id}`, { method: 'DELETE' }),
  },
  biblioteca: {
    resumen: () => peticion<ResumenBiblioteca>('/biblioteca/resumen'),
  },
  usuarios: {
    listar: () => peticion<UsuarioAdmin[]>('/usuarios'),
    crear: (entrada: UsuarioEntrada) => peticion<UsuarioAdmin>('/usuarios', json(entrada)),
    actualizar: (id: string, cambios: UsuarioActualizacion) => peticion<UsuarioAdmin>(`/usuarios/${id}`, json(cambios, 'PATCH')),
    eliminar: (id: string) => peticion<void>(`/usuarios/${id}`, { method: 'DELETE' }),
  },
}
