import { Pencil, RotateCcw } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { useEditarDescripcion } from '@/api/consultas'
import type { CotizacionItem } from '@/api/tipos'
import { Boton } from '@/componentes/Boton'

/**
 * Texto de la partida para esta cotización. No toca el catálogo ni el sistema de la empresa: es una
 * nota del vendedor sobre el concepto de esa partida. Si está lleno, es lo que se imprime (y no se
 * manda a traducir, porque es una corrección deliberada).
 */
export function DescripcionEditable({ item, cotizacionId }: { item: CotizacionItem; cotizacionId: string }) {
  const editar = useEditarDescripcion(cotizacionId)
  const [editando, setEditando] = useState(false)
  const [texto, setTexto] = useState('')
  const campo = useRef<HTMLTextAreaElement>(null)

  const editada = Boolean(item.descripcion_editada.trim())
  const visible = editada ? item.descripcion_editada : item.descripcion_origen

  useEffect(() => {
    if (editando) campo.current?.focus()
  }, [editando])

  const abrir = () => {
    setTexto(visible)
    setEditando(true)
  }

  const guardar = (valor: string) => {
    const limpio = valor.trim()
    // Si queda igual que la del sistema, se guarda vacío: vuelve a seguir al sistema.
    const descripcion = limpio === item.descripcion_origen.trim() ? '' : limpio
    if (descripcion === item.descripcion_editada) {
      setEditando(false)
      return
    }
    editar.mutate({ itemId: item.id, descripcion }, { onSuccess: () => setEditando(false) })
  }

  if (editando) {
    return (
      <div className="max-w-md">
        <textarea
          ref={campo}
          rows={3}
          value={texto}
          maxLength={600}
          disabled={editar.isPending}
          onChange={(evento) => setTexto(evento.target.value)}
          onKeyDown={(evento) => {
            if (evento.key === 'Escape') setEditando(false)
            if (evento.key === 'Enter' && (evento.metaKey || evento.ctrlKey)) guardar(texto)
          }}
          className="w-full"
          aria-label={`Descripción de ${item.descripcion_origen}`}
        />
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <Boton cargando={editar.isPending} onClick={() => guardar(texto)}>
            Guardar
          </Boton>
          <Boton variante="fantasma" disabled={editar.isPending} onClick={() => setEditando(false)}>
            Cancelar
          </Boton>
          {editada && (
            <Boton
              variante="fantasma"
              icono={<RotateCcw className="h-4 w-4" />}
              disabled={editar.isPending}
              onClick={() => guardar('')}
              title="Volver a la descripción del sistema"
            >
              Restaurar
            </Boton>
          )}
        </div>
        <p className="mt-1 text-xs text-texto-secundario">Sólo para esta cotización. Ctrl+Enter guarda, Esc cancela.</p>
      </div>
    )
  }

  return (
    <div className="group max-w-md">
      <button
        type="button"
        onClick={abrir}
        className="block w-full text-left hover:text-acento"
        title="Editar la descripción para esta cotización"
      >
        <span>{visible}</span>
        <Pencil className="ml-1.5 inline h-3.5 w-3.5 align-baseline text-texto-secundario opacity-0 transition-opacity group-hover:opacity-100" />
      </button>
      {editada && <p className="text-xs text-texto-secundario">Editada · el sistema dice: {item.descripcion_origen}</p>}
      {!editada && item.item && item.item.nombre !== item.descripcion_origen && (
        <p className="text-xs text-texto-secundario">Catálogo: {item.item.nombre}</p>
      )}
    </div>
  )
}
