import { RefreshCw } from 'lucide-react'

import { usePerfil, useSalud } from '@/api/consultas'
import { Aviso, mensajeDeError } from '@/componentes/Aviso'
import { Boton } from '@/componentes/Boton'
import { Pildora } from '@/componentes/Pildora'

const NOMBRES: Record<string, string> = {
  supabase: 'Conexión a Supabase',
  buckets: 'Buckets de Storage',
  catalogo: 'Catálogo',
  usuarios: 'Usuarios',
  weasyprint: 'WeasyPrint (PDF)',
  proveedor_imagenes: 'Proveedor de imágenes',
  mapeo_columnas: 'Mapeo de columnas del export',
}

const API = ((import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000').replace(/\/$/, '')

export function Estado() {
  const perfil = usePerfil()
  const salud = useSalud()

  if (perfil.isLoading) return <p className="text-texto-secundario">Cargando…</p>
  if (perfil.data?.rol !== 'admin') return <Aviso tono="ambar">Esta sección es sólo para administradores.</Aviso>

  const datos = salud.data
  const tono = datos?.estado === 'ok' ? 'resuelto' : datos?.estado === 'degradado' ? 'pendiente' : 'conceptual'

  return (
    <div>
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl">Estado del sistema</h1>
          <p className="mt-1 text-texto-secundario">
            Diagnóstico de <code className="rounded bg-fondo px-1">{API}/api/salud</code>. Es lo primero que conviene revisar después de un deploy.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {datos && (
            <Pildora tono={tono}>
              {datos.estado === 'ok' ? 'Todo en orden' : datos.estado === 'degradado' ? 'Con pendientes' : 'Caído'}
            </Pildora>
          )}
          <Boton variante="secundario" icono={<RefreshCw className="h-4 w-4" />} cargando={salud.isFetching} onClick={() => void salud.refetch()}>
            Volver a revisar
          </Boton>
        </div>
      </header>

      {salud.isError && (
        <Aviso tono="error" className="mt-6">
          {mensajeDeError(salud.error)}
        </Aviso>
      )}

      {datos && (
        <>
          <p className="mt-6 text-sm text-texto-secundario">
            Versión {datos.version} · entorno {datos.entorno} · proveedor de imágenes {datos.proveedor_imagenes}
          </p>
          <ul className="tarjeta mt-3 divide-y divide-borde">
            {Object.entries(datos.verificaciones).map(([clave, verificacion]) => (
              <li key={clave} className="flex items-start gap-4 px-5 py-4">
                <span
                  className={`mt-1.5 h-3 w-3 shrink-0 rounded-full ${verificacion.ok ? 'bg-resuelto-texto' : 'bg-conceptual-texto'}`}
                  aria-label={verificacion.ok ? 'Correcto' : 'Con problema'}
                />
                <div className="min-w-0">
                  <p className="font-medium">{NOMBRES[clave] ?? clave}</p>
                  <p className="break-words text-sm text-texto-secundario">{verificacion.detalle}</p>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
