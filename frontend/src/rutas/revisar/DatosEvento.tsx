import { CalendarDays } from 'lucide-react'
import { useState } from 'react'

import { useGuardarEvento } from '@/api/consultas'
import type { CotizacionDetalle } from '@/api/tipos'
import { Aviso, mensajeDeError } from '@/componentes/Aviso'
import { Boton } from '@/componentes/Boton'
import { Campo } from '@/componentes/Campo'
import { moneda } from '@/lib/formato'

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

/** 3 -> '3 días', 1 -> '1 día', 1.5 -> '1.5 días'. */
export const textoDias = (dias: number) => `${dias} día${dias === 1 ? '' : 's'}`

const numero = (texto: string) => (texto.trim() === '' ? NaN : Number(texto.replace(',', '.')))
const valido = (dias: number) => Number.isFinite(dias) && dias > 0 && dias <= 365

/**
 * Fecha del evento, vendedor y días. Llegan del export del sistema ("Fecha de evento:", "Atendió:",
 * "DIAS:") y aquí se corrigen. El mobiliario se cobra por día: los días cobrados mueven el subtotal.
 */
export function DatosEvento({ cotizacion, className = '' }: { cotizacion: CotizacionDetalle; className?: string }) {
  const guardar = useGuardarEvento(cotizacion.id)
  const [inicio, setInicio] = useState(cotizacion.fecha_evento ?? '')
  const [fin, setFin] = useState(cotizacion.fecha_evento_fin ?? '')
  const [variosDias, setVariosDias] = useState(Boolean(cotizacion.fecha_evento_fin))
  const [vendedor, setVendedor] = useState(cotizacion.vendedor)
  const [renta, setRenta] = useState(String(cotizacion.dias_renta))
  const [iguales, setIguales] = useState(cotizacion.dias_cobrados === null)
  const [cobrados, setCobrados] = useState(String(cotizacion.dias_cobrados_efectivos))

  const finEfectivo = variosDias && fin ? fin : ''
  const alReves = Boolean(finEfectivo) && Boolean(inicio) && finEfectivo < inicio
  const diasRenta = numero(renta)
  const diasCobrados = iguales ? diasRenta : numero(cobrados)
  const diasMal = !valido(diasRenta) || !valido(diasCobrados)

  const guardado = {
    fecha_evento: cotizacion.fecha_evento ?? '',
    fecha_evento_fin: cotizacion.fecha_evento_fin ?? '',
    vendedor: cotizacion.vendedor,
    dias_renta: cotizacion.dias_renta,
    dias_cobrados: cotizacion.dias_cobrados,
  }
  const cambios =
    inicio !== guardado.fecha_evento ||
    finEfectivo !== guardado.fecha_evento_fin ||
    vendedor.trim() !== guardado.vendedor ||
    diasRenta !== guardado.dias_renta ||
    (iguales ? null : diasCobrados) !== guardado.dias_cobrados

  const enviar = () =>
    guardar.mutate({
      fecha_evento: inicio || null,
      fecha_evento_fin: finEfectivo || null,
      vendedor: vendedor.trim(),
      dias_renta: diasRenta,
      dias_cobrados: iguales ? null : diasCobrados,
    })

  return (
    <section className={`tarjeta p-5 ${className}`} aria-labelledby="titulo-datos-evento">
      <h2 id="titulo-datos-evento" className="flex items-center gap-2 text-base font-semibold">
        <CalendarDays className="h-4 w-4" aria-hidden />
        Datos del evento
      </h2>
      <p className="mt-1 text-sm text-texto-secundario">
        Vienen del PDF del sistema; aquí se corrigen. La fecha, el vendedor y los días salen en el encabezado de la propuesta.
      </p>

      <div className="mt-4 grid gap-x-8 gap-y-3 md:grid-cols-2">
        <div className="flex flex-col gap-3">
          <Campo etiqueta={variosDias ? 'Primer día del evento' : 'Día del evento'}>
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
            <Campo etiqueta="Último día del evento">
              <input type="date" value={fin} min={inicio || undefined} onChange={(e) => setFin(e.target.value)} />
            </Campo>
          )}
          <Campo etiqueta="Vendedor">
            <input value={vendedor} maxLength={80} onChange={(e) => setVendedor(e.target.value)} placeholder="Quién atiende al cliente" />
          </Campo>
        </div>

        <div className="flex flex-col gap-3">
          <Campo etiqueta="Días de renta" ayuda="Cuántos días tiene el cliente el mobiliario.">
            <input
              type="number"
              inputMode="decimal"
              min={0.5}
              max={365}
              step={0.5}
              value={renta}
              onChange={(e) => {
                setRenta(e.target.value)
                if (iguales) setCobrados(e.target.value)
              }}
            />
          </Campo>
          <label className="flex items-center gap-2 text-sm text-texto-secundario">
            <input
              type="checkbox"
              className="h-4 w-4"
              checked={iguales}
              onChange={(e) => {
                setIguales(e.target.checked)
                if (e.target.checked) setCobrados(renta)
              }}
            />
            Días de renta = días cobrados
          </label>
          <Campo
            etiqueta="Días cobrados"
            ayuda={iguales ? 'Desmarca la casilla si por promoción o acuerdo se cobran otros.' : 'El mobiliario se multiplica por éstos.'}
          >
            <input
              type="number"
              inputMode="decimal"
              min={0.5}
              max={365}
              step={0.5}
              value={iguales ? renta : cobrados}
              disabled={iguales}
              onChange={(e) => setCobrados(e.target.value)}
            />
          </Campo>
        </div>
      </div>

      {alReves && (
        <Aviso tono="ambar" className="mt-3">
          El evento no puede terminar antes de empezar.
        </Aviso>
      )}
      {diasMal && (
        <Aviso tono="ambar" className="mt-3">
          Los días tienen que ser un número mayor que cero (se vale medio día: 1.5).
        </Aviso>
      )}
      {!inicio && (
        <Aviso tono="ambar" className="mt-3">
          Sin fecha, la propuesta sale sin fecha en el encabezado.
        </Aviso>
      )}
      {!diasMal && diasCobrados !== cotizacion.dias_sistema && (
        <Aviso tono="ambar" className="mt-3">
          En el sistema son {textoDias(cotizacion.dias_sistema)} cobrados. Si aquí cobras {textoDias(diasCobrados)}, cámbialo también allá
          para que la factura salga igual.
        </Aviso>
      )}

      {!diasMal && (
        <p className="mt-3 text-sm text-texto-secundario">
          Mobiliario: {moneda(cotizacion.subtotal_por_dia)} por día × {textoDias(diasCobrados)} ={' '}
          <span className="font-medium text-texto tabular-nums">{moneda(cotizacion.subtotal_por_dia * diasCobrados)}</span>
          {inicio && !alReves && (
            <>
              {' '}
              · Evento: <span className="font-medium text-texto">{textoEvento(inicio, finEfectivo || null)}</span>
            </>
          )}
        </p>
      )}
      {guardar.isError && (
        <Aviso tono="error" className="mt-3">
          {mensajeDeError(guardar.error)}
        </Aviso>
      )}

      <div className="mt-4 flex justify-end">
        <Boton variante="secundario" disabled={!cambios || alReves || diasMal} cargando={guardar.isPending} onClick={enviar}>
          Guardar datos del evento
        </Boton>
      </div>
    </section>
  )
}
