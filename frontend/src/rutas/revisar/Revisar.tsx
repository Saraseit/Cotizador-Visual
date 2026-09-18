import { createColumnHelper, flexRender, getCoreRowModel, useReactTable } from '@tanstack/react-table'
import { ArrowRight, ImagePlus, RefreshCw } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { useCotizacion } from '@/api/consultas'
import type { CotizacionItem } from '@/api/tipos'
import { Aviso, mensajeDeError } from '@/componentes/Aviso'
import { Boton } from '@/componentes/Boton'
import { Miniatura } from '@/componentes/Miniatura'
import { PildoraEstadoItem } from '@/componentes/Pildora'
import { cantidad, moneda } from '@/lib/formato'

import { SelectorImagen } from './SelectorImagen'

type Filtro = 'pendientes' | 'todos'

const columna = createColumnHelper<CotizacionItem>()

export function Revisar() {
  const { id } = useParams<{ id: string }>()
  const navegar = useNavigate()
  const consulta = useCotizacion(id)
  const [filtro, setFiltro] = useState<Filtro>('pendientes')
  const [itemAbierto, setItemAbierto] = useState<CotizacionItem | null>(null)

  const cotizacion = consulta.data
  const pendientes = cotizacion?.items_pendientes ?? 0
  const total = cotizacion?.total_items ?? 0
  const resueltos = total - pendientes

  const filas = useMemo(() => {
    const items = [...(cotizacion?.items ?? [])].sort((a, b) => {
      const pesoA = a.estado === 'falta_imagen' ? 0 : 1
      const pesoB = b.estado === 'falta_imagen' ? 0 : 1
      return pesoA - pesoB || a.orden - b.orden
    })
    return filtro === 'pendientes' ? items.filter((i) => i.estado === 'falta_imagen') : items
  }, [cotizacion, filtro])

  const columnas = useMemo(
    () => [
      columna.display({
        id: 'miniatura',
        header: 'Imagen',
        cell: ({ row }) => (
          <Miniatura url={row.original.imagen?.url} conceptual={row.original.es_render_conceptual} alt={row.original.descripcion_origen} />
        ),
      }),
      columna.accessor('codigo_origen', {
        header: 'Código',
        cell: ({ getValue, row }) => (
          <div>
            <span className="font-medium">{getValue() || '—'}</span>
            {row.original.tipo_item === 'ad_hoc' && <p className="text-xs text-texto-secundario">Fuera de catálogo</p>}
          </div>
        ),
      }),
      columna.accessor('descripcion_origen', {
        header: 'Descripción',
        cell: ({ getValue, row }) => (
          <div className="max-w-md">
            <p>{getValue()}</p>
            {row.original.item && row.original.item.nombre !== getValue() && (
              <p className="text-xs text-texto-secundario">Catálogo: {row.original.item.nombre}</p>
            )}
          </div>
        ),
      }),
      columna.accessor('cantidad', {
        header: () => <span className="block text-right">Cantidad</span>,
        cell: ({ getValue }) => <span className="block text-right tabular-nums">{cantidad(getValue())}</span>,
      }),
      columna.accessor('precio_unitario', {
        header: () => <span className="block text-right">Precio</span>,
        cell: ({ getValue }) => <span className="block text-right tabular-nums">{moneda(getValue())}</span>,
      }),
      columna.accessor('estado', {
        header: 'Estado',
        cell: ({ getValue }) => <PildoraEstadoItem estado={getValue()} />,
      }),
      columna.display({
        id: 'accion',
        header: '',
        cell: ({ row }) => {
          const falta = row.original.estado === 'falta_imagen'
          return (
            <Boton
              variante={falta ? 'primario' : 'secundario'}
              icono={falta ? <ImagePlus className="h-4 w-4" /> : <RefreshCw className="h-4 w-4" />}
              onClick={() => setItemAbierto(row.original)}
            >
              {falta ? 'Elegir imagen' : 'Cambiar'}
            </Boton>
          )
        },
      }),
    ],
    [],
  )

  const tabla = useReactTable({ data: filas, columns: columnas, getCoreRowModel: getCoreRowModel() })

  if (consulta.isLoading) return <p className="text-texto-secundario">Cargando cotización…</p>
  if (consulta.isError || !cotizacion) {
    return (
      <Aviso tono="error">
        {consulta.error ? mensajeDeError(consulta.error) : 'No se encontró la cotización.'}{' '}
        <Link to="/" className="underline">
          Volver
        </Link>
      </Aviso>
    )
  }

  const porcentaje = total === 0 ? 0 : Math.round((resueltos / total) * 100)

  return (
    <div className="pb-28">
      <header className="flex flex-wrap items-end justify-between gap-6">
        <div>
          <p className="text-sm text-texto-secundario">Paso 2 · Revisar imágenes</p>
          <h1 className="mt-1 text-3xl">{cotizacion.nombre_cliente}</h1>
          <p className="mt-1 text-texto-secundario">
            Referencia {cotizacion.referencia_externa || 'sin referencia'} · {total} ítems · total {moneda(cotizacion.total)}
          </p>
        </div>
        <div className="w-full max-w-xs">
          <div className="flex items-baseline justify-between text-sm">
            <span className={pendientes > 0 ? 'font-medium text-pendiente-texto' : 'font-medium text-resuelto-texto'}>
              {pendientes > 0 ? `${pendientes} de ${total} necesitan revisión` : 'Todos los ítems tienen imagen'}
            </span>
            <span className="text-texto-secundario">{porcentaje}%</span>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-pildora bg-borde" role="progressbar" aria-valuenow={porcentaje} aria-valuemin={0} aria-valuemax={100}>
            <div className="h-full rounded-pildora bg-resuelto-texto transition-all" style={{ width: `${porcentaje}%` }} />
          </div>
        </div>
      </header>

      <div className="mt-8 flex items-center gap-2" role="tablist" aria-label="Filtro de ítems">
        {(
          [
            ['pendientes', `Pendientes (${pendientes})`],
            ['todos', `Todos (${total})`],
          ] as const
        ).map(([valor, texto]) => (
          <button
            key={valor}
            type="button"
            role="tab"
            aria-selected={filtro === valor}
            onClick={() => setFiltro(valor)}
            className={`min-h-boton rounded-pildora border px-4 text-sm font-medium transition-colors ${
              filtro === valor ? 'border-texto bg-texto text-superficie' : 'border-borde bg-superficie text-texto-secundario hover:text-texto'
            }`}
          >
            {texto}
          </button>
        ))}
      </div>

      <div className="tarjeta mt-4 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="border-b border-borde bg-fondo/60 text-left text-xs uppercase tracking-wide text-texto-secundario">
            {tabla.getHeaderGroups().map((grupo) => (
              <tr key={grupo.id}>
                {grupo.headers.map((encabezado) => (
                  <th key={encabezado.id} className="px-4 py-3 font-semibold">
                    {flexRender(encabezado.column.columnDef.header, encabezado.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="divide-y divide-borde">
            {tabla.getRowModel().rows.length === 0 && (
              <tr>
                <td colSpan={columnas.length} className="px-4 py-10 text-center text-texto-secundario">
                  {filtro === 'pendientes' ? (
                    <>
                      No hay ítems pendientes.{' '}
                      <button type="button" className="underline" onClick={() => setFiltro('todos')}>
                        Ver todos
                      </button>
                    </>
                  ) : (
                    'Esta cotización no tiene ítems.'
                  )}
                </td>
              </tr>
            )}
            {tabla.getRowModel().rows.map((fila) => (
              <tr key={fila.id} className={fila.original.estado === 'falta_imagen' ? 'bg-pendiente-fondo' : 'bg-superficie'}>
                {fila.getVisibleCells().map((celda) => (
                  <td key={celda.id} className="px-4 py-3 align-middle">
                    {flexRender(celda.column.columnDef.cell, celda.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-borde bg-superficie/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <p className="text-sm text-texto-secundario">
            {pendientes > 0
              ? `${pendientes} ítem${pendientes === 1 ? '' : 's'} sin imagen saldrá${pendientes === 1 ? '' : 'n'} con el marcador "Sin imagen".`
              : 'Todo listo para generar la propuesta.'}
          </p>
          <Boton icono={<ArrowRight className="h-4 w-4" />} onClick={() => navegar(`/cotizaciones/${cotizacion.id}/generar`)}>
            Generar propuesta
          </Boton>
        </div>
      </div>

      {itemAbierto && (
        <SelectorImagen
          item={cotizacion.items.find((i) => i.id === itemAbierto.id) ?? itemAbierto}
          cotizacionId={cotizacion.id}
          alCerrar={() => setItemAbierto(null)}
        />
      )}
    </div>
  )
}
