import { supabase } from '@/lib/supabase'

import type {
  CatalogoItem,
  CotizacionDetalle,
  CotizacionResumen,
  Imagen,
  ResultadoGeneracion,
  ResultadoPdf,
  ResumenBiblioteca,
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
  return (await respuesta.json()) as T
}

export const api = {
  cotizaciones: {
    listar: () => peticion<CotizacionResumen[]>('/cotizaciones'),
    obtener: (id: string) => peticion<CotizacionDetalle>(`/cotizaciones/${id}`),
    crear: (archivo: File) => {
      const datos = new FormData()
      datos.append('archivo', archivo)
      return peticion<CotizacionDetalle>('/cotizaciones', { method: 'POST', body: datos })
    },
    asignarImagen: (cotizacionId: string, itemId: string, imagenId: string | null) =>
      peticion<CotizacionDetalle>(`/cotizaciones/${cotizacionId}/items/${itemId}`, {
        method: 'PATCH',
        body: JSON.stringify({ imagen_id: imagenId }),
      }),
    generar: (id: string) => peticion<ResultadoPdf>(`/cotizaciones/${id}/generar`, { method: 'POST' }),
  },
  catalogo: {
    buscar: (termino: string) => peticion<CatalogoItem[]>(`/catalogo/items?buscar=${encodeURIComponent(termino)}`),
    imagenesDeItem: (itemId: string) => peticion<Imagen[]>(`/catalogo/items/${itemId}/imagenes`),
  },
  imagenes: {
    subir: (parametros: { archivo: File; itemId?: string | null; etiquetas?: string[]; tipo?: 'oficial' | 'variante' }) => {
      const datos = new FormData()
      datos.append('archivo', parametros.archivo)
      if (parametros.itemId) datos.append('item_id', parametros.itemId)
      if (parametros.etiquetas?.length) datos.append('etiquetas', parametros.etiquetas.join(','))
      if (parametros.tipo) datos.append('tipo', parametros.tipo)
      return peticion<Imagen>('/imagenes', { method: 'POST', body: datos })
    },
    generar: (cuerpo: { item_id: string; imagen_base_id: string; peticion: string }) =>
      peticion<ResultadoGeneracion>('/imagenes/generar', { method: 'POST', body: JSON.stringify(cuerpo) }),
  },
  biblioteca: {
    resumen: () => peticion<ResumenBiblioteca>('/biblioteca/resumen'),
  },
}
