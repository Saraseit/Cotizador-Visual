import { RotateCcw } from 'lucide-react'
import { useState } from 'react'

import { useAlinear, useRestaurarPartida } from '@/api/consultas'
import type { Alineacion, CambioSistema } from '@/api/tipos'
import { cantidad, moneda } from '@/lib/formato'

import { mensajeDeError } from './Aviso'
import { Boton } from './Boton'

const seccion = (valor: CambioSistema['antes']) => (valor ? String(valor) : 'sin sección')
const signo = (valor: number) => `${valor > 0 ? '+' : '−'}${moneda(Math.abs(valor))}`

/** Un renglón por cambio; los cambios de sección iguales (MESAS → CEREMONIA) se juntan en uno. */
function renglones(cambios: CambioSistema[]) {
  const secciones = new Map<string, CambioSistema[]>()
  const otros: CambioSistema[] = []
  for (const cambio of cambios) {
    if (cambio.tipo !== 'seccion') otros.push(cambio)
    else {
      const llave = `${cambio.antes ?? ''}→${cambio.despues ?? ''}`
      secciones.set(llave, [...(secciones.get(llave) ?? []), cambio])
    }
  }
  return { otros, secciones: [...secciones.values()] }
}

function Cambio({ cambio, alRestaurar, restaurando }: { cambio: CambioSistema; alRestaurar: () => void; restaurando: boolean }) {
  const nombre = <span className="font-medium">{cambio.descripcion}</span>
  switch (cambio.tipo) {
    case 'agregada':
      return (
        <>
          Agregada: {nombre} · {moneda(Number(cambio.despues ?? 0))}
        </>
      )
    case 'quitada':
      return (
        <span className="inline-flex flex-wrap items-center gap-x-2">
          <span>
            Quitada: {nombre} · {moneda(Number(cambio.antes ?? 0))}
          </span>
          <button type="button" onClick={alRestaurar} disabled={restaurando} className="inline-flex items-center gap-1 underline">
            <RotateCcw className="h-3 w-3" aria-hidden /> Restaurar
          </button>
        </span>
      )
    case 'cantidad':
      return (
        <>
          Cantidad de {nombre}: {cantidad(Number(cambio.antes))} → {cantidad(Number(cambio.despues))}
        </>
      )
    case 'precio':
      return (
        <>
          Precio de {nombre}: {moneda(Number(cambio.antes))} → {moneda(Number(cambio.despues))}
        </>
      )
    default:
      return null
  }
}

/**
 * "Cotización no alineada al sistema principal": cambios hechos en Revisar (partidas agregadas o
 * quitadas, cantidades, precios, secciones) que el sistema todavía no tiene. No bloquea los PDF. Al
 * marcar la casilla, lo de ProVista pasa a ser lo del sistema y el aviso desaparece.
 */
export function AvisoAlineacion({ cotizacionId, alineacion, className = '' }: { cotizacionId: string; alineacion: Alineacion; className?: string }) {
  const alinear = useAlinear(cotizacionId)
  const restaurar = useRestaurarPartida(cotizacionId)
  const [marcada, setMarcada] = useState(false)
  if (alineacion.alineada) return null
  const { otros, secciones } = renglones(alineacion.cambios)
  const error = alinear.error ?? restaurar.error

  return (
    <div role="alert" className={`rounded-boton border border-alerta-borde bg-alerta-fondo px-4 py-3 text-sm text-alerta-texto ${className}`}>
      <p className="font-semibold">Cotización no alineada al sistema principal</p>
      <p className="mt-1">
        Se hicieron cambios en ProVista que el sistema principal todavía no tiene. Los PDF se pueden generar igual; cuando se confirmen,
        aplícalos también en el sistema.
      </p>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        {otros.map((cambio) => (
          <li key={`${cambio.tipo}:${cambio.item_id}`}>
            <Cambio cambio={cambio} restaurando={restaurar.isPending} alRestaurar={() => restaurar.mutate(cambio.item_id)} />
          </li>
        ))}
        {secciones.map((grupo) => (
          <li key={`seccion:${grupo[0].antes}→${grupo[0].despues}`}>
            {grupo.length === 1 ? <span className="font-medium">{grupo[0].descripcion}</span> : `${grupo.length} partidas`}: de la sección{' '}
            {seccion(grupo[0].antes)} a {seccion(grupo[0].despues)}
          </li>
        ))}
      </ul>
      {Math.abs(alineacion.diferencia_importe) >= 0.005 && (
        <p className="mt-2">
          El subtotal cambió <span className="font-semibold tabular-nums">{signo(alineacion.diferencia_importe)}</span> antes de IVA
          respecto al sistema.
        </p>
      )}
      {error && <p className="mt-2 font-medium">{mensajeDeError(error)}</p>}
      <div className="mt-3 border-t border-alerta-borde pt-3">
        <label className="flex cursor-pointer items-start gap-2 font-medium">
          <input type="checkbox" className="mt-0.5 h-4 w-4 accent-alerta-texto" checked={marcada} onChange={(e) => setMarcada(e.target.checked)} />
          Estos cambios ya están aplicados en el sistema principal
        </label>
        {marcada && (
          <div className="mt-2 flex flex-wrap items-center gap-3 pl-6">
            <span>Lo que está en ProVista pasará a ser lo del sistema y el aviso desaparecerá. Queda en el historial.</span>
            <Boton cargando={alinear.isPending} onClick={() => alinear.mutate(undefined, { onSuccess: () => setMarcada(false) })}>
              Confirmar
            </Boton>
            <Boton variante="fantasma" onClick={() => setMarcada(false)}>
              Cancelar
            </Boton>
          </div>
        )}
      </div>
    </div>
  )
}
