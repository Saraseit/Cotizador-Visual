import { Plus } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import { useActualizarListaPrecios, useCrearListaPrecios, useListasPrecios } from '@/api/consultas'
import type { ListaPrecios as Lista } from '@/api/tipos'
import { Aviso, mensajeDeError } from '@/componentes/Aviso'
import { Boton } from '@/componentes/Boton'
import { Modal } from '@/componentes/Modal'

function FilaLista({ lista }: { lista: Lista }) {
  const [nombre, setNombre] = useState(lista.nombre)
  const actualizar = useActualizarListaPrecios()
  const cambiado = nombre.trim() !== lista.nombre && nombre.trim().length > 0

  return (
    <li className="flex flex-wrap items-center gap-3 py-3">
      <input value={nombre} onChange={(e) => setNombre(e.target.value)} className="min-w-[200px] flex-1" aria-label={`Nombre de la lista ${lista.nombre}`} />
      <Boton
        variante="secundario"
        disabled={!cambiado}
        cargando={actualizar.isPending}
        onClick={() => actualizar.mutate({ id: lista.id, cambios: { nombre: nombre.trim() } })}
      >
        Renombrar
      </Boton>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          className="h-4 w-4"
          checked={lista.activo}
          onChange={(e) => actualizar.mutate({ id: lista.id, cambios: { activo: e.target.checked } })}
        />
        Activa
      </label>
      {actualizar.isError && <span className="w-full text-xs text-conceptual-texto">{mensajeDeError(actualizar.error)}</span>}
    </li>
  )
}

export function ListasPrecios({ alCerrar }: { alCerrar: () => void }) {
  const listas = useListasPrecios()
  const crear = useCrearListaPrecios()
  const [nueva, setNueva] = useState('')

  const agregar = (evento: FormEvent) => {
    evento.preventDefault()
    if (!nueva.trim()) return
    crear.mutate(nueva.trim(), { onSuccess: () => setNueva('') })
  }

  return (
    <Modal abierto titulo="Listas de precios" subtitulo="Cada ítem del catálogo puede tener un precio por lista." alCerrar={alCerrar}>
      <div className="flex flex-col gap-4">
        {listas.isError && <Aviso tono="error">{mensajeDeError(listas.error)}</Aviso>}
        <ul className="divide-y divide-borde">
          {listas.data?.map((lista) => (
            <FilaLista key={lista.id} lista={lista} />
          ))}
          {listas.data?.length === 0 && <li className="py-3 text-sm text-texto-secundario">Todavía no hay listas.</li>}
        </ul>

        <form onSubmit={agregar} className="flex flex-wrap items-end gap-3 border-t border-borde pt-4">
          <label className="flex min-w-[200px] flex-1 flex-col gap-1.5 text-sm font-medium">
            Nueva lista
            <input value={nueva} onChange={(e) => setNueva(e.target.value)} placeholder="Mayoreo" />
          </label>
          <Boton type="submit" icono={<Plus className="h-4 w-4" />} cargando={crear.isPending} disabled={!nueva.trim()}>
            Agregar
          </Boton>
          {crear.isError && <span className="w-full text-xs text-conceptual-texto">{mensajeDeError(crear.error)}</span>}
        </form>
        <p className="text-xs text-texto-secundario">
          Desactivar una lista la oculta del formulario y de la tabla sin borrar los precios ya capturados.
        </p>
      </div>
    </Modal>
  )
}
