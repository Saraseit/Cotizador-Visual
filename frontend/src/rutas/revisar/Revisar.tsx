import { createColumnHelper, flexRender, getCoreRowModel, useReactTable } from '@tanstack/react-table'
import { ArrowRight, ImagePlus, RefreshCw } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'

import { useAsignarCargo, useCotizacion, usePresentacion, useReordenar } from '@/api/consultas'
import type { Cargo, CotizacionItem } from '@/api/tipos'
import { Aviso, mensajeDeError } from '@/componentes/Aviso'
import { Boton } from '@/componentes/Boton'
import { Miniatura } from '@/componentes/Miniatura'
import { PildoraEstadoItem } from '@/componentes/Pildora'
import { cantidad, formatoDinero } from '@/lib/formato'

import { DescripcionEditable } from './DescripcionEditable'
import { FormatoPropuesta } from './FormatoPropuesta'
import { SelectorImagen } from './SelectorImagen'
import { TablaOrdenable } from './TablaOrdenable'

type Filtro = 'pendientes' | 'todos'

const columna = createColumnHelper<CotizacionItem>()

/** Partida normal o cargo (flete/montaje). Los cargos no se imprimen como partida: se suman abajo. */
function SelectorTipo({ item, alCambiar, ocupado }: { item: CotizacionItem; alCambiar: (cargo: Cargo | null) => void; ocupado: boolean }) {
  return (
    <select
      aria-label={`Tipo de ${item.descripcion_origen}`}
      value={item.cargo ?? ''}
      disabled={ocupado}
      onChange={(e) => alCambiar((e.target.value || null) as Cargo | null)}
      className="min-w-[7.5rem]"
    >
      <option value="">Partida</option>
      <option value="flete">Flete</option>
      <option value="montaje">Montaje</option>
    </select>
  )
}

export function Revisar() {
  const { id } = useParams<{ id: string }>()
  const navegar = useNavigate()
  const consulta = useCotizacion(id)
  // Viene de Subir: cuántas fotos del PDF quedaron guardadas en la biblioteca.
  const fotosImportadas = (useLocation().state as { fotosImportadas?: number } | null)?.fotosImportadas ?? 0
  const [filtro, setFiltro] = useState<Filtro>('pendientes')
  const [itemAbierto, setItemAbierto] = useState<CotizacionItem | null>(null)
  const presentacion = usePresentacion(id)
  const reordenar = useReordenar(id ?? '')
  const asignarCargo = useAsignarCargo(id ?? '')

  const cotizacion = consulta.data
  // Moneda e idioma salen de la presentación: la tabla muestra lo mismo que va a imprimir el PDF.
  const config = presentacion.data?.config
  const dinero = formatoDinero(config?.moneda ?? 'MXN', config?.tipo_cambio ?? null)
  const traducciones = config && config.idioma !== 'es' ? config.traducciones : {}
  const pendientes = cotizacion?.items_pendientes ?? 0
  const total = cotizacion?.total_items ?? 0
  const resueltos = total - pendientes

  // Flete y montaje no son partidas: no se revisan ni se ordenan, se suman en los totales.
  // "Todos" sigue el orden de impresión (el que se arrastra); "Pendientes" sólo las que faltan.
  const filas = useMemo(() => {
    const partidas = (cotizacion?.items ?? []).filter((i) => !i.cargo).sort((a, b) => a.orden - b.orden)
    return filtro === 'pendientes' ? partidas.filter((i) => i.estado === 'falta_imagen') : partidas
  }, [cotizacion, filtro])
  const cargos = useMemo(() => (cotizacion?.items ?? []).filter((i) => i.cargo), [cotizacion])

  const { mutate: mutarCargo, isPending: cambiandoCargo } = asignarCargo
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
        cell: ({ row }) => (
          <DescripcionEditable item={row.original} cotizacionId={id ?? ''} traduccion={traducciones[row.original.descripcion_origen]} />
        ),
      }),
      columna.accessor('cantidad', {
        header: () => <span className="block text-right">Cantidad</span>,
        cell: ({ getValue }) => <span className="block text-right tabular-nums">{cantidad(getValue())}</span>,
      }),
      columna.accessor('precio_unitario', {
        header: () => <span className="block text-right">Precio</span>,
        cell: ({ getValue }) => <span className="block text-right tabular-nums">{dinero(getValue())}</span>,
      }),
      columna.accessor('estado', {
        header: 'Estado',
        cell: ({ getValue }) => <PildoraEstadoItem estado={getValue()} />,
      }),
      columna.display({
        id: 'tipo',
        header: 'Tipo',
        cell: ({ row }) => (
          <SelectorTipo
            item={row.original}
            ocupado={cambiandoCargo}
            alCambiar={(cargo) => mutarCargo({ itemId: row.original.id, cargo })}
          />
        ),
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
    // `dinero` y `traducciones` dependen de la moneda y el idioma elegidos.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [mutarCargo, cambiandoCargo, id, config?.moneda, config?.tipo_cambio, config?.idioma, traducciones],
  )

  const tabla = useReactTable({
    data: filas,
    columns: columnas,
    getCoreRowModel: getCoreRowModel(),
    getRowId: (item) => item.id,
    // El tipo se cambia sólo en "Todos"; "Pendientes" se queda como estaba.
    state: { columnVisibility: { tipo: filtro === 'todos' } },
  })

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
  const columnasVisibles = tabla.getVisibleLeafColumns().length
  const ordenando = filtro === 'todos' && filas.length > 0

  const encabezado = (
    <thead className="border-b border-borde bg-fondo/60 text-left text-xs uppercase tracking-wide text-texto-secundario">
      {tabla.getHeaderGroups().map((grupo) => (
        <tr key={grupo.id}>
          {ordenando && (
            <th className="w-10 py-3 pl-2">
              <span className="sr-only">Mover</span>
            </th>
          )}
          {grupo.headers.map((cabecera) => (
            <th key={cabecera.id} className="px-4 py-3 font-semibold">
              {flexRender(cabecera.column.columnDef.header, cabecera.getContext())}
            </th>
          ))}
        </tr>
      ))}
    </thead>
  )

  const totales: [string, number][] = [
    ['Subtotal', cotizacion.subtotal],
    ...(cotizacion.flete !== 0 ? ([['Flete', cotizacion.flete]] as [string, number][]) : []),
    ...(cotizacion.montaje !== 0 ? ([['Montaje', cotizacion.montaje]] as [string, number][]) : []),
    ...(cotizacion.iva !== null ? ([['IVA', cotizacion.iva]] as [string, number][]) : []),
  ]

  return (
    <div className="pb-28">
      <header className="flex flex-wrap items-end justify-between gap-6">
        <div>
          <p className="text-sm text-texto-secundario">Paso 2 · Revisar imágenes</p>
          <h1 className="mt-1 text-3xl">{cotizacion.nombre_cliente}</h1>
          <p className="mt-1 text-texto-secundario">
            Referencia {cotizacion.referencia_externa || 'sin referencia'} · {total} ítems · total {dinero(cotizacion.total)}
            {cotizacion.iva === null && ' más IVA'}
          </p>
        </div>
        <div className="w-full max-w-xs">
          <div className="flex items-baseline justify-between text-sm">
            <span className={pendientes > 0 ? 'font-medium text-pendiente-texto' : 'font-medium text-resuelto-texto'}>
              {pendientes > 0 ? `${pendientes} de ${total} necesitan revisión` : 'Todos los ítems tienen imagen'}
            </span>
            <span className="text-texto-secundario">{porcentaje}%</span>
          </div>
          <div
            className="mt-2 h-2 overflow-hidden rounded-pildora bg-borde"
            role="progressbar"
            aria-valuenow={porcentaje}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div className="h-full rounded-pildora bg-resuelto-texto transition-all" style={{ width: `${porcentaje}%` }} />
          </div>
        </div>
      </header>

      {fotosImportadas > 0 && (
        <Aviso tono="info" className="mt-6">
          Se {fotosImportadas === 1 ? 'guardó 1 foto' : `guardaron ${fotosImportadas} fotos`} del PDF en la biblioteca de sus artículos. Ya
          están asignadas a las partidas de esta cotización.
        </Aviso>
      )}

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
              filtro === valor
                ? 'border-texto bg-texto text-superficie'
                : 'border-borde bg-superficie text-texto-secundario hover:text-texto'
            }`}
          >
            {texto}
          </button>
        ))}
      </div>

      {ordenando && filas.length > 1 && (
        <p className="mt-3 text-sm text-texto-secundario">
          Arrastra desde el asa para cambiar el orden en que se imprimen las partidas. Desde el título de una sección la mueves completa.
        </p>
      )}
      {reordenar.isError && (
        <Aviso tono="error" className="mt-3">
          No se guardó el nuevo orden: {mensajeDeError(reordenar.error)}
        </Aviso>
      )}
      {asignarCargo.isError && (
        <Aviso tono="error" className="mt-3">
          No se cambió el tipo: {mensajeDeError(asignarCargo.error)}
        </Aviso>
      )}

      <div className="tarjeta mt-4 overflow-x-auto">
        {ordenando ? (
          <TablaOrdenable
            filas={tabla.getRowModel().rows}
            columnas={columnasVisibles}
            encabezado={encabezado}
            alReordenar={(ids) => reordenar.mutate(ids)}
          />
        ) : (
          <table className="w-full text-sm">
            {encabezado}
            <tbody className="divide-y divide-borde">
              {tabla.getRowModel().rows.length === 0 && (
                <tr>
                  <td colSpan={columnasVisibles} className="px-4 py-10 text-center text-texto-secundario">
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
        )}
      </div>

      {filtro === 'todos' && (
        <div className="mt-6 grid gap-6 md:grid-cols-[1fr_20rem]">
          <section className="tarjeta p-5" aria-labelledby="titulo-cargos">
            <h2 id="titulo-cargos" className="text-base font-semibold">
              Flete y montaje
            </h2>
            <p className="mt-1 text-sm text-texto-secundario">
              No se imprimen como partida: se suman en los totales. Se detectan por la descripción. Si alguno está mal, cámbialo aquí o en
              la columna Tipo.
            </p>
            {cargos.length === 0 ? (
              <p className="mt-4 text-sm text-texto-secundario">Esta cotización no trae flete ni montaje.</p>
            ) : (
              <ul className="mt-4 divide-y divide-borde">
                {cargos.map((item) => (
                  <li key={item.id} className="flex flex-wrap items-center gap-3 py-3 text-sm">
                    <div className="min-w-0 flex-1">
                      <p className="truncate" title={item.descripcion_origen}>
                        {item.descripcion_origen}
                      </p>
                      {item.codigo_origen && <p className="text-xs text-texto-secundario">{item.codigo_origen}</p>}
                    </div>
                    <span className="tabular-nums">{dinero(item.importe)}</span>
                    <SelectorTipo item={item} ocupado={cambiandoCargo} alCambiar={(cargo) => mutarCargo({ itemId: item.id, cargo })} />
                  </li>
                ))}
              </ul>
            )}
          </section>

          <div className="space-y-6">
            {config && <FormatoPropuesta cotizacionId={id ?? ''} config={config} />}

            <section className="tarjeta p-5" aria-label="Totales de la propuesta">
              <dl className="space-y-2 text-sm">
                {totales.map(([nombre, valor]) => (
                  <div key={nombre} className="flex justify-between gap-4">
                    <dt className="text-texto-secundario">{nombre}</dt>
                    <dd className="tabular-nums">{dinero(valor)}</dd>
                  </div>
                ))}
                <div className="flex justify-between gap-4 border-t border-borde pt-2 text-base font-semibold">
                  <dt>
                    Total
                    {cotizacion.iva === null && <span className="font-normal text-texto-secundario"> (más IVA)</span>}
                  </dt>
                  <dd className="tabular-nums">{dinero(cotizacion.total)}</dd>
                </div>
              </dl>
            </section>
          </div>
        </div>
      )}

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
