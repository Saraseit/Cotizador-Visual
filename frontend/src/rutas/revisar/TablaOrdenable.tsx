import {
  closestCenter,
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type CollisionDetection,
  type DragEndEvent,
  type DragStartEvent,
} from '@dnd-kit/core'
import { arrayMove, SortableContext, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { flexRender, type Row } from '@tanstack/react-table'
import { GripVertical } from 'lucide-react'
import { forwardRef, useMemo, useState, type ButtonHTMLAttributes, type ReactNode } from 'react'

import type { CotizacionItem } from '@/api/tipos'

/** Bloque de partidas consecutivas de la misma sección, en el orden de impresión. */
export interface Seccion {
  id: string // "sec:<n>:<título>": estable al mover partidas o la sección
  titulo: string
  filas: Row<CotizacionItem>[]
}

export function agruparEnSecciones(filas: Row<CotizacionItem>[]): Seccion[] {
  const secciones: Seccion[] = []
  const vistas = new Map<string, number>()
  for (const fila of filas) {
    const titulo = fila.original.categoria
    const ultima = secciones[secciones.length - 1]
    if (ultima && ultima.titulo === titulo) {
      ultima.filas.push(fila)
    } else {
      const vez = vistas.get(titulo) ?? 0
      vistas.set(titulo, vez + 1)
      secciones.push({ id: `sec:${vez}:${titulo}`, titulo, filas: [fila] })
    }
  }
  return secciones
}

const esSeccion = (id: unknown) => String(id).startsWith('sec:')

const Agarradera = forwardRef<HTMLButtonElement, { etiqueta: string } & ButtonHTMLAttributes<HTMLButtonElement>>(function Agarradera(
  { etiqueta, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      type="button"
      aria-label={etiqueta}
      title="Arrastra para cambiar el orden (con teclado: Espacio y flechas)"
      className="flex h-9 w-7 cursor-grab touch-none items-center justify-center rounded-boton text-texto-secundario hover:bg-fondo hover:text-texto focus:outline-none focus-visible:ring-2 focus-visible:ring-acento/40 active:cursor-grabbing"
      {...props}
    >
      <GripVertical className="h-4 w-4" aria-hidden />
    </button>
  )
})

function FilaPartida({ fila }: { fila: Row<CotizacionItem> }) {
  const { attributes, listeners, setNodeRef, setActivatorNodeRef, transform, transition, isDragging } = useSortable({
    id: fila.original.id,
  })
  return (
    <tr
      ref={setNodeRef}
      style={{ transform: CSS.Translate.toString(transform), transition }}
      className={`${fila.original.estado === 'falta_imagen' ? 'bg-pendiente-fondo' : 'bg-superficie'} ${
        isDragging ? 'relative z-10 shadow-lg ring-2 ring-acento/40' : ''
      }`}
    >
      <td className="w-10 py-3 pl-2 align-middle">
        <Agarradera etiqueta={`Mover ${fila.original.descripcion_origen}`} ref={setActivatorNodeRef} {...attributes} {...listeners} />
      </td>
      {fila.getVisibleCells().map((celda) => (
        <td key={celda.id} className="px-4 py-3 align-middle">
          {flexRender(celda.column.columnDef.cell, celda.getContext())}
        </td>
      ))}
    </tr>
  )
}

function EncabezadoSeccion({ seccion, columnas, arrastrable }: { seccion: Seccion; columnas: number; arrastrable: boolean }) {
  const { attributes, listeners, setNodeRef, setActivatorNodeRef, transform, transition, isDragging } = useSortable({
    id: seccion.id,
    disabled: !arrastrable,
  })
  return (
    <tr
      ref={setNodeRef}
      style={{ transform: CSS.Translate.toString(transform), transition }}
      className={`bg-fondo/60 ${isDragging ? 'relative z-10 shadow-lg ring-2 ring-acento/40' : ''}`}
    >
      <td className="w-10 py-2 pl-2 align-middle">
        {arrastrable && (
          <Agarradera
            etiqueta={`Mover la sección ${seccion.titulo || 'sin sección'}`}
            ref={setActivatorNodeRef}
            {...attributes}
            {...listeners}
          />
        )}
      </td>
      <td colSpan={columnas} className="px-4 py-2 align-middle">
        <span className="text-xs font-semibold uppercase tracking-wide text-texto-secundario">{seccion.titulo || 'Sin sección'}</span>
        <span className="ml-2 text-xs text-texto-secundario">
          {seccion.filas.length} {seccion.filas.length === 1 ? 'partida' : 'partidas'}
        </span>
      </td>
    </tr>
  )
}

interface Props {
  filas: Row<CotizacionItem>[]
  columnas: number
  encabezado: ReactNode
  /** Recibe los ids de todas las partidas en el nuevo orden. */
  alReordenar: (ids: string[]) => void
}

/**
 * Tabla de la vista "Todos": partidas agrupadas por sección en el orden de impresión.
 * Se arrastran partidas dentro de su sección y secciones completas (al tomar una sección, todas se
 * pliegan a su título para que se vea claro dónde va a caer).
 */
export function TablaOrdenable({ filas, columnas, encabezado, alReordenar }: Props) {
  const secciones = useMemo(() => agruparEnSecciones(filas), [filas])
  const [moviendoSeccion, setMoviendoSeccion] = useState(false)
  const conEncabezados = secciones.length > 1 || secciones.some((s) => s.titulo)

  const sensores = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  )

  const seccionDe = useMemo(() => {
    const mapa = new Map<string, string>()
    for (const s of secciones) for (const f of s.filas) mapa.set(f.original.id, s.id)
    return mapa
  }, [secciones])

  // Una sección sólo cae entre secciones; una partida sólo dentro de su propia sección.
  const colision: CollisionDetection = (args) => {
    const activo = String(args.active.id)
    const destinos = args.droppableContainers.filter((c) =>
      esSeccion(activo) ? esSeccion(c.id) : !esSeccion(c.id) && seccionDe.get(String(c.id)) === seccionDe.get(activo),
    )
    return closestCenter({ ...args, droppableContainers: destinos })
  }

  const alEmpezar = (evento: DragStartEvent) => setMoviendoSeccion(esSeccion(evento.active.id))

  const alSoltar = ({ active, over }: DragEndEvent) => {
    setMoviendoSeccion(false)
    if (!over || active.id === over.id) return
    let nuevas = secciones.map((s) => ({
      ...s,
      ids: s.filas.map((f) => f.original.id),
    }))
    if (esSeccion(active.id)) {
      const desde = nuevas.findIndex((s) => s.id === active.id)
      const hasta = nuevas.findIndex((s) => s.id === over.id)
      if (desde < 0 || hasta < 0) return
      nuevas = arrayMove(nuevas, desde, hasta)
    } else {
      const seccion = nuevas.find((s) => s.ids.includes(String(active.id)))
      if (!seccion || !seccion.ids.includes(String(over.id))) return
      seccion.ids = arrayMove(seccion.ids, seccion.ids.indexOf(String(active.id)), seccion.ids.indexOf(String(over.id)))
    }
    alReordenar(nuevas.flatMap((s) => s.ids))
  }

  return (
    <DndContext
      sensors={sensores}
      collisionDetection={colision}
      onDragStart={alEmpezar}
      onDragEnd={alSoltar}
      onDragCancel={() => setMoviendoSeccion(false)}
    >
      <table className="w-full text-sm">
        {encabezado}
        <SortableContext items={secciones.map((s) => s.id)} strategy={verticalListSortingStrategy}>
          {secciones.map((seccion) => (
            <tbody key={seccion.id} className="divide-y divide-borde border-b border-borde">
              {conEncabezados && <EncabezadoSeccion seccion={seccion} columnas={columnas} arrastrable={secciones.length > 1} />}
              {!moviendoSeccion && (
                <SortableContext items={seccion.filas.map((f) => f.original.id)} strategy={verticalListSortingStrategy}>
                  {seccion.filas.map((fila) => (
                    <FilaPartida key={fila.original.id} fila={fila} />
                  ))}
                </SortableContext>
              )}
            </tbody>
          ))}
        </SortableContext>
      </table>
    </DndContext>
  )
}
