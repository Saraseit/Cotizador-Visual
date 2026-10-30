import { CalendarDays } from 'lucide-react'
import { useState } from 'react'

import { useGuardarFechaEvento } from '@/api/consultas'
import { Aviso, mensajeDeError } from '@/componentes/Aviso'
import { Boton } from '@/componentes/Boton'
import { Campo } from '@/componentes/Campo'

/** 'AAAA-MM-DD' -> 'dd/mm/aaaa', sin pasar por Date (que lo interpretaría en UTC y restaría un día). */
const comoSeLee = (iso: string) => iso.split('-').reverse().join('/')

/** Lo mismo que imprime el PDF: un día suelto, o el rango sin repetir lo que ya se dijo. */
export function textoEvento(inicio: string | null, fin: string | null): string {
  if (!inicio) return ''
  if (!fin || fin === inicio) return comoSeLee(inicio)
  const [anoI, mesI, diaI] = inicio.split('-')
  const [anoF, mesF] = fin.split('-')
  if (anoI === anoF && mesI === mesF) return `${diaI} al ${comoSeLee(fin)}`
  if (anoI === anoF) return `${diaI}/${mesI} al ${comoSeLee(fin)}`
  return `${comoSeLee(inicio)} al ${comoSeLee(fin)}`
}

/**
 * Cuándo es el evento. El export del sistema no lo trae, así que se captura aquí: es la fecha que
 * sale en el encabezado de la propuesta (antes salía la del día en que se generaba el PDF).
 */
export function FechaEvento({
  cotizacionId,
  fechaEvento,
  fechaEventoFin,
  className = '',
}: {
  cotizacionId: string
  fechaEvento: string | null
  fechaEventoFin: string | null
  className?: string
}) {
  const guardar = useGuardarFechaEvento(cotizacionId)
  const [inicio, setInicio] = useState(fechaEvento ?? '')
  const [fin, setFin] = useState(fechaEventoFin ?? '')
  const [variosDias, setVariosDias] = useState(Boolean(fechaEventoFin))

  const finEfectivo = variosDias && fin ? fin : ''
  const alReves = Boolean(finEfectivo) && Boolean(inicio) && finEfectivo < inicio
  const cambios = inicio !== (fechaEvento ?? '') || finEfectivo !== (fechaEventoFin ?? '')
  const vistaPrevia = textoEvento(inicio || null, finEfectivo || null)

  const enviar = () => guardar.mutate({ fecha_evento: inicio || null, fecha_evento_fin: finEfectivo || null })

  return (
    <section className={`tarjeta p-5 ${className}`} aria-labelledby="titulo-fecha-evento">
      <h2 id="titulo-fecha-evento" className="flex items-center gap-2 text-base font-semibold">
        <CalendarDays className="h-4 w-4" aria-hidden />
        Fecha del evento
      </h2>
      <p className="mt-1 text-sm text-texto-secundario">
        Es la fecha que sale en el encabezado de la propuesta. El sistema no la trae, hay que ponerla aquí.
      </p>

      <div className="mt-4 flex flex-col gap-3">
        <Campo etiqueta={variosDias ? 'Primer día' : 'Día del evento'}>
          <input type="date" value={inicio} onChange={(e) => setInicio(e.target.value)} />
        </Campo>
        <label className="flex items-center gap-2 text-sm text-texto-secundario">
          <input
            type="checkbox"
            className="h-4 w-4"
            checked={variosDias}
            onChange={(e) => {
              setVariosDias(e.target.checked)
              if (!e.target.checked) setFin('')
            }}
          />
          El evento dura varios días
        </label>
        {variosDias && (
          <Campo etiqueta="Último día">
            <input type="date" value={fin} min={inicio || undefined} onChange={(e) => setFin(e.target.value)} />
          </Campo>
        )}
      </div>

      {alReves && (
        <Aviso tono="ambar" className="mt-3">
          El evento no puede terminar antes de empezar.
        </Aviso>
      )}
      {!inicio && (
        <Aviso tono="ambar" className="mt-3">
          Sin fecha, la propuesta sale sin fecha en el encabezado.
        </Aviso>
      )}
      {vistaPrevia && !alReves && (
        <p className="mt-3 text-sm text-texto-secundario">
          En el PDF saldrá: <span className="font-medium text-texto">{vistaPrevia}</span>
        </p>
      )}
      {guardar.isError && (
        <Aviso tono="error" className="mt-3">
          {mensajeDeError(guardar.error)}
        </Aviso>
      )}

      <div className="mt-4 flex justify-end">
        <Boton variante="secundario" disabled={!cambios || alReves} cargando={guardar.isPending} onClick={enviar}>
          Guardar fecha
        </Boton>
      </div>
    </section>
  )
}
