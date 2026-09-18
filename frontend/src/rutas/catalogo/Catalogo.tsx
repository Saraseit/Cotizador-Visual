import { ClipboardPaste, Pencil, Plus, Search, Tags } from 'lucide-react'
import { useDeferredValue, useState } from 'react'

import { useCatalogo, useListasPrecios } from '@/api/consultas'
import type { CatalogoItem } from '@/api/tipos'
import { Aviso, mensajeDeError } from '@/componentes/Aviso'
import { Boton } from '@/componentes/Boton'
import { Miniatura } from '@/componentes/Miniatura'
import { Pildora } from '@/componentes/Pildora'
import { moneda } from '@/lib/formato'

import { CargaTexto } from './CargaTexto'
import { FormularioItem } from './FormularioItem'
import { ListasPrecios } from './ListasPrecios'

type Ventana = { tipo: 'nuevo' } | { tipo: 'editar'; item: CatalogoItem } | { tipo: 'texto' } | { tipo: 'listas' } | null

export function Catalogo() {
  const [buscar, setBuscar] = useState('')
  const busqueda = useDeferredValue(buscar.trim())
  const items = useCatalogo(busqueda)
  const listas = useListasPrecios()
  const [ventana, setVentana] = useState<Ventana>(null)

  const listasActivas = (listas.data ?? []).filter((l) => l.activo)

  return (
    <div>
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl">Catálogo</h1>
          <p className="mt-1 text-texto-secundario">
            Ítems con su foto oficial, medidas, etiquetas, precios por lista y costo de reposición.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Boton variante="secundario" icono={<Tags className="h-4 w-4" />} onClick={() => setVentana({ tipo: 'listas' })}>
            Listas de precios
          </Boton>
          <Boton variante="secundario" icono={<ClipboardPaste className="h-4 w-4" />} onClick={() => setVentana({ tipo: 'texto' })}>
            Carga por texto
          </Boton>
          <Boton icono={<Plus className="h-4 w-4" />} onClick={() => setVentana({ tipo: 'nuevo' })}>
            Nuevo ítem
          </Boton>
        </div>
      </header>

      <div className="relative mt-6 max-w-md">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-texto-secundario" />
        <input
          type="search"
          value={buscar}
          onChange={(evento) => setBuscar(evento.target.value)}
          placeholder="Buscar por código, nombre o categoría"
          className="w-full pl-9"
          aria-label="Buscar en el catálogo"
        />
      </div>

      {items.isError && (
        <Aviso tono="error" className="mt-4">
          {mensajeDeError(items.error)}
        </Aviso>
      )}

      <div className="tarjeta mt-4 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="border-b border-borde bg-fondo/60 text-left text-xs uppercase tracking-wide text-texto-secundario">
            <tr>
              <th className="px-4 py-3 font-semibold">Foto</th>
              <th className="px-4 py-3 font-semibold">Código</th>
              <th className="px-4 py-3 font-semibold">Nombre</th>
              <th className="px-4 py-3 font-semibold">Medidas</th>
              <th className="px-4 py-3 font-semibold">Etiquetas</th>
              {listasActivas.map((lista) => (
                <th key={lista.id} className="px-4 py-3 text-right font-semibold">
                  {lista.nombre}
                </th>
              ))}
              <th className="px-4 py-3 text-right font-semibold">Reposición</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-borde">
            {items.isLoading && (
              <tr>
                <td colSpan={7 + listasActivas.length} className="px-4 py-10 text-center text-texto-secundario">
                  Cargando catálogo…
                </td>
              </tr>
            )}
            {items.data?.length === 0 && (
              <tr>
                <td colSpan={7 + listasActivas.length} className="px-4 py-10 text-center text-texto-secundario">
                  {busqueda ? 'Ningún ítem coincide con la búsqueda.' : 'El catálogo está vacío. Crea el primer ítem o pega una lista.'}
                </td>
              </tr>
            )}
            {items.data?.map((item) => {
              const precioPorLista = new Map(item.precios.map((p) => [p.lista_id, p.precio]))
              return (
                <tr key={item.id} className={item.activo ? 'bg-superficie' : 'bg-fondo/60 text-texto-secundario'}>
                  <td className="px-4 py-3">
                    <Miniatura url={item.imagen_oficial?.url} alt={item.nombre} />
                  </td>
                  <td className="px-4 py-3 align-top">
                    <span className="font-medium">{item.codigo}</span>
                    {!item.activo && (
                      <div className="mt-1">
                        <Pildora tono="neutro">Inactivo</Pildora>
                      </div>
                    )}
                  </td>
                  <td className="max-w-xs px-4 py-3 align-top">
                    <p className="font-medium">{item.nombre}</p>
                    <p className="text-xs text-texto-secundario">{item.categoria || 'Sin categoría'}</p>
                    {item.descripcion && <p className="mt-1 line-clamp-2 text-xs text-texto-secundario">{item.descripcion}</p>}
                  </td>
                  <td className="px-4 py-3 align-top text-texto-secundario">{item.medidas || '—'}</td>
                  <td className="max-w-[200px] px-4 py-3 align-top">
                    <div className="flex flex-wrap gap-1">
                      {item.etiquetas.length === 0 && <span className="text-texto-secundario">—</span>}
                      {item.etiquetas.map((e) => (
                        <Pildora key={e} tono="neutro">
                          {e}
                        </Pildora>
                      ))}
                    </div>
                  </td>
                  {listasActivas.map((lista) => {
                    const precio = precioPorLista.get(lista.id)
                    return (
                      <td key={lista.id} className="px-4 py-3 text-right align-top tabular-nums">
                        {precio === undefined ? <span className="text-texto-secundario">—</span> : moneda(precio)}
                      </td>
                    )
                  })}
                  <td className="px-4 py-3 text-right align-top tabular-nums">
                    {item.costo_reposicion === null ? <span className="text-texto-secundario">—</span> : moneda(item.costo_reposicion)}
                  </td>
                  <td className="px-4 py-3 text-right align-top">
                    <Boton variante="secundario" icono={<Pencil className="h-4 w-4" />} onClick={() => setVentana({ tipo: 'editar', item })}>
                      Editar
                    </Boton>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {items.data && items.data.length >= 100 && (
        <p className="mt-2 text-xs text-texto-secundario">Se muestran los primeros 100 resultados; afina la búsqueda para ver otros.</p>
      )}

      {(ventana?.tipo === 'nuevo' || ventana?.tipo === 'editar') && (
        <FormularioItem
          item={ventana.tipo === 'editar' ? ventana.item : null}
          listas={listasActivas}
          alCerrar={() => setVentana(null)}
          alCrear={(item) => setVentana({ tipo: 'editar', item })}
        />
      )}
      {ventana?.tipo === 'texto' && <CargaTexto alCerrar={() => setVentana(null)} />}
      {ventana?.tipo === 'listas' && <ListasPrecios alCerrar={() => setVentana(null)} />}
    </div>
  )
}
