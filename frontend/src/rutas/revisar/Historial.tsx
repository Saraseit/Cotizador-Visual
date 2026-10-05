import { ChevronDown, History } from 'lucide-react'
import { useState } from 'react'

import { useHistorial } from '@/api/consultas'
import { Aviso, mensajeDeError } from '@/componentes/Aviso'
import { fechaHora } from '@/lib/formato'

const VISIBLES = 8

/** Historial de cambios hechos en Revisar: quién, cuándo y qué (agregar, quitar, cantidades, precios…). */
export function Historial({ cotizacionId }: { cotizacionId: string }) {
  const consulta = useHistorial(cotizacionId)
  const [todos, setTodos] = useState(false)
  const cambios = consulta.data ?? []
  const visibles = todos ? cambios : cambios.slice(0, VISIBLES)

  return (
    <section className="tarjeta p-5" aria-labelledby="titulo-historial">
      <h2 id="titulo-historial" className="flex items-center gap-2 text-base font-semibold">
        <History className="h-4 w-4" aria-hidden /> Historial de cambios
      </h2>
      {consulta.isError && (
        <Aviso tono="error" className="mt-3">
          {mensajeDeError(consulta.error)}
        </Aviso>
      )}
      {consulta.isLoading ? (
        <p className="mt-3 text-sm text-texto-secundario">Cargando…</p>
      ) : cambios.length === 0 ? (
        <p className="mt-3 text-sm text-texto-secundario">Sin cambios: la cotización está como vino del sistema.</p>
      ) : (
        <ol className="mt-3 divide-y divide-borde">
          {visibles.map((cambio) => (
            <li key={cambio.id} className="py-2 text-sm">
              <p>{cambio.descripcion}</p>
              <p className="text-xs text-texto-secundario">
                {fechaHora(cambio.creado_en)}
                {cambio.usuario_nombre && ` · ${cambio.usuario_nombre}`}
              </p>
            </li>
          ))}
        </ol>
      )}
      {cambios.length > VISIBLES && (
        <button type="button" onClick={() => setTodos(!todos)} className="mt-2 inline-flex items-center gap-1 text-sm text-texto-secundario hover:text-texto">
          <ChevronDown className={`h-4 w-4 transition-transform ${todos ? 'rotate-180' : ''}`} />
          {todos ? 'Ver menos' : `Ver los ${cambios.length}`}
        </button>
      )}
    </section>
  )
}
