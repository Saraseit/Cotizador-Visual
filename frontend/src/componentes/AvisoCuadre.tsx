import type { Cuadre } from '@/api/tipos'
import { moneda } from '@/lib/formato'

import { Aviso } from './Aviso'

/** Diferencias de menos de 50 centavos son redondeos del sistema (igual que en el backend). */
const TOLERANCIA = 0.5

const conSigno = (valor: number) => `${valor > 0 ? '+' : '−'}${moneda(Math.abs(valor))}`

/**
 * Aviso en rojo cuando el total de la propuesta no es el del PDF del sistema que se subió: un artículo
 * compuesto con otro precio o una partida que no se leyó bien. Los importes van en pesos, como el PDF
 * del sistema, aunque la propuesta se presente en dólares.
 */
export function AvisoCuadre({ cuadre, className = '' }: { cuadre: Cuadre; className?: string }) {
  if (cuadre.cuadra) return null
  const lecturaDudosa =
    cuadre.subtotal_documento !== null && Math.abs(cuadre.suma_partidas - cuadre.subtotal_documento) >= TOLERANCIA

  return (
    <Aviso tono="alerta" className={className}>
      <p className="font-semibold">Esta propuesta no cuadra con el PDF del sistema.</p>
      <p className="mt-1">
        Total del PDF: <span className="tabular-nums">{moneda(cuadre.total_documento)}</span> · Total de la propuesta:{' '}
        <span className="tabular-nums">{moneda(cuadre.total_propuesta)}</span> · Diferencia:{' '}
        <span className="font-semibold tabular-nums">{conSigno(cuadre.diferencia)}</span>
      </p>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        {cuadre.ajustes.map((ajuste) => (
          <li key={ajuste.compuesto_id}>
            <span className="font-medium">{ajuste.nombre}</span>: sus partidas suman {moneda(ajuste.importe_partidas)} y se presenta en{' '}
            {moneda(ajuste.importe)} ({conSigno(ajuste.importe - ajuste.importe_partidas)}).
          </li>
        ))}
        {lecturaDudosa && (
          <li>
            Las partidas leídas suman {moneda(cuadre.suma_partidas)}, pero el SubTotal impreso en el PDF es{' '}
            {moneda(cuadre.subtotal_documento as number)}: puede que alguna partida no se haya leído bien. Compáralo con el PDF original.
          </li>
        )}
      </ul>
      {cuadre.ajustes.length > 0 && (
        <p className="mt-2">
          Si el PDF traía IVA, se ajustó en la misma proporción. Si el cambio de precio es correcto, actualiza también la cotización en el
          sistema.
        </p>
      )}
    </Aviso>
  )
}
