import { useState } from 'react'

import { useRenombrarSeccion } from '@/api/consultas'
import { Aviso, mensajeDeError } from '@/componentes/Aviso'
import { Boton } from '@/componentes/Boton'
import { Campo } from '@/componentes/Campo'
import { Modal } from '@/componentes/Modal'

const NUEVA = '\u0000nueva'

export const nombreSeccion = (titulo: string) => titulo || 'Sin sección'

/**
 * Sección de una partida: una de las que ya tiene la cotización o una nueva ("CEREMONIA", "COCKTAIL").
 * Las del sistema vienen de inicio; las nuevas nacen al asignarlas a una partida.
 */
export function SelectorSeccion({
  secciones,
  valor,
  alCambiar,
  etiqueta = 'Sección',
}: {
  secciones: string[]
  valor: string
  alCambiar: (valor: string) => void
  etiqueta?: string
}) {
  const [nueva, setNueva] = useState(!secciones.includes(valor) && valor !== '')
  return (
    <Campo etiqueta={etiqueta}>
      <div className="flex flex-col gap-2">
        <select
          value={nueva ? NUEVA : valor}
          onChange={(e) => {
            const elegido = e.target.value
            setNueva(elegido === NUEVA)
            alCambiar(elegido === NUEVA ? '' : elegido)
          }}
        >
          {secciones.map((s) => (
            <option key={s} value={s}>
              {nombreSeccion(s)}
            </option>
          ))}
          {!secciones.includes('') && <option value="">Sin sección</option>}
          <option value={NUEVA}>Nueva sección…</option>
        </select>
        {nueva && (
          <input autoFocus value={valor} maxLength={120} placeholder="Ej. CEREMONIA o COCKTAIL" onChange={(e) => alCambiar(e.target.value)} />
        )}
      </div>
    </Campo>
  )
}

/**
 * Renombrar una sección, o quitarla pasando sus partidas a otra (internamente es lo mismo: si el
 * nombre nuevo ya existe, las secciones se juntan).
 */
export function ModalSeccion({
  cotizacionId,
  titulo,
  secciones,
  modo,
  alCerrar,
}: {
  cotizacionId: string
  titulo: string
  secciones: string[]
  modo: 'renombrar' | 'quitar'
  alCerrar: () => void
}) {
  const renombrar = useRenombrarSeccion(cotizacionId)
  const otras = secciones.filter((s) => s !== titulo)
  const [destino, setDestino] = useState(modo === 'renombrar' ? titulo : (otras[0] ?? ''))
  const junta = otras.some((s) => s.toLowerCase() === destino.trim().toLowerCase())
  const listo = modo === 'quitar' ? otras.includes(destino) : destino.trim() !== titulo

  return (
    <Modal
      abierto
      titulo={modo === 'renombrar' ? 'Renombrar sección' : 'Quitar sección'}
      subtitulo={nombreSeccion(titulo)}
      alCerrar={alCerrar}
    >
      <div className="flex flex-col gap-4">
        {modo === 'renombrar' ? (
          <Campo etiqueta="Nombre" ayuda="Si escribes el nombre de otra sección, las dos se juntan.">
            <input autoFocus value={destino} maxLength={120} onChange={(e) => setDestino(e.target.value)} />
          </Campo>
        ) : otras.length === 0 ? (
          <Aviso tono="ambar">Es la única sección de la cotización: renómbrala en vez de quitarla.</Aviso>
        ) : (
          <Campo etiqueta="Pasar sus partidas a" ayuda="La sección desaparece; sus partidas quedan al final de la que elijas.">
            <select value={destino} onChange={(e) => setDestino(e.target.value)}>
              {otras.map((s) => (
                <option key={s} value={s}>
                  {nombreSeccion(s)}
                </option>
              ))}
            </select>
          </Campo>
        )}
        {modo === 'renombrar' && junta && <Aviso tono="info">Ya hay una sección con ese nombre: sus partidas se juntarán.</Aviso>}
        <p className="text-xs text-texto-secundario">Queda en el historial y marca la cotización como no alineada al sistema principal.</p>
        {renombrar.isError && <Aviso tono="error">{mensajeDeError(renombrar.error)}</Aviso>}
        <div className="flex justify-end gap-2 border-t border-borde pt-4">
          <Boton variante="fantasma" onClick={alCerrar}>
            Cancelar
          </Boton>
          <Boton disabled={!listo} cargando={renombrar.isPending} onClick={() => renombrar.mutate({ de: titulo, a: destino }, { onSuccess: alCerrar })}>
            {modo === 'renombrar' ? 'Guardar' : 'Quitar sección'}
          </Boton>
        </div>
      </div>
    </Modal>
  )
}
