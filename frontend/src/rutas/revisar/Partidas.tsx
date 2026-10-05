import { Plus, Search, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { useAgregarPartida, useCatalogo, useEditarPartida, useQuitarPartida } from '@/api/consultas'
import type { CatalogoItem, CotizacionItem } from '@/api/tipos'
import { Aviso, mensajeDeError } from '@/componentes/Aviso'
import { Boton } from '@/componentes/Boton'
import { Campo } from '@/componentes/Campo'
import { Miniatura } from '@/componentes/Miniatura'
import { Modal } from '@/componentes/Modal'
import { cantidad as formatoCantidad, moneda } from '@/lib/formato'

import { SelectorSeccion } from './Secciones'

const numero = (texto: string) => {
  const valor = Number(texto.replace(/[$,\s]/g, ''))
  return texto.trim() && Number.isFinite(valor) ? valor : null
}

const AVISO_SISTEMA = 'Queda en el historial y marca la cotización como no alineada al sistema principal. No bloquea los PDF.'

// ---------------------------------------------------------------------------
// Agregar
// ---------------------------------------------------------------------------

/** Partida que no viene en el PDF del sistema: del catálogo (con su código y foto) o fuera de él. */
export function AgregarPartida({
  cotizacionId,
  secciones,
  seccionInicial,
  alCerrar,
}: {
  cotizacionId: string
  secciones: string[]
  seccionInicial: string
  alCerrar: () => void
}) {
  const agregar = useAgregarPartida(cotizacionId)
  const [modo, setModo] = useState<'catalogo' | 'libre'>('catalogo')
  const [buscar, setBuscar] = useState('')
  const catalogo = useCatalogo(buscar)
  const [articulo, setArticulo] = useState<CatalogoItem | null>(null)
  const [codigo, setCodigo] = useState('')
  const [descripcion, setDescripcion] = useState('')
  const [cantidad, setCantidad] = useState('1')
  const [precio, setPrecio] = useState('')
  const [seccion, setSeccion] = useState(seccionInicial)

  const elegir = (item: CatalogoItem) => {
    setArticulo(item)
    setDescripcion(item.nombre)
    setPrecio(item.precios[0] ? String(item.precios[0].precio) : '')
  }

  const valorCantidad = numero(cantidad)
  const valorPrecio = numero(precio)
  const listo =
    descripcion.trim() !== '' && valorCantidad !== null && valorCantidad > 0 && valorPrecio !== null && valorPrecio >= 0 && (modo === 'libre' || articulo)

  const guardar = () =>
    agregar.mutate(
      {
        item_id: modo === 'catalogo' ? (articulo?.id ?? null) : null,
        codigo: modo === 'libre' ? codigo.trim() : '',
        descripcion: descripcion.trim(),
        cantidad: valorCantidad as number,
        precio_unitario: valorPrecio as number,
        categoria: seccion,
      },
      { onSuccess: alCerrar },
    )

  return (
    <Modal abierto titulo="Agregar partida" subtitulo="Fuera del PDF del sistema" alCerrar={alCerrar}>
      <div className="flex flex-col gap-4">
        <div className="flex gap-1 border-b border-borde" role="tablist">
          {(
            [
              ['catalogo', 'Del catálogo'],
              ['libre', 'Fuera de catálogo'],
            ] as const
          ).map(([valor, texto]) => (
            <button
              key={valor}
              type="button"
              role="tab"
              aria-selected={modo === valor}
              onClick={() => setModo(valor)}
              className={`-mb-px min-h-boton border-b-2 px-4 text-sm font-medium ${
                modo === valor ? 'border-acento text-texto' : 'border-transparent text-texto-secundario hover:text-texto'
              }`}
            >
              {texto}
            </button>
          ))}
        </div>

        {modo === 'catalogo' && (
          <div className="flex flex-col gap-2">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-texto-secundario" />
              <input
                autoFocus
                className="w-full pl-9"
                placeholder="Buscar por código o nombre…"
                aria-label="Buscar en el catálogo"
                value={buscar}
                onChange={(e) => setBuscar(e.target.value)}
              />
            </div>
            {catalogo.isError && <Aviso tono="error">{mensajeDeError(catalogo.error)}</Aviso>}
            <ul className="max-h-56 divide-y divide-borde overflow-y-auto rounded-tarjeta border border-borde" aria-label="Resultados">
              {(catalogo.data ?? []).slice(0, 30).map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => elegir(item)}
                    className={`flex w-full items-center gap-3 px-3 py-2 text-left text-sm hover:bg-fondo ${articulo?.id === item.id ? 'bg-acento-suave/40' : ''}`}
                  >
                    <Miniatura url={item.imagen_oficial?.url} alt={item.nombre} />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate">{item.nombre}</span>
                      <span className="text-xs text-texto-secundario">{item.codigo}</span>
                    </span>
                    {item.precios[0] && <span className="tabular-nums text-texto-secundario">{moneda(item.precios[0].precio)}</span>}
                  </button>
                </li>
              ))}
              {catalogo.data?.length === 0 && <li className="px-3 py-4 text-sm text-texto-secundario">Sin resultados.</li>}
            </ul>
          </div>
        )}

        {(modo === 'libre' || articulo) && (
          <div className="grid gap-4 sm:grid-cols-2">
            {modo === 'libre' && (
              <Campo etiqueta="Código" ayuda="Opcional. Si es de un artículo del catálogo, toma su foto.">
                <input value={codigo} maxLength={40} onChange={(e) => setCodigo(e.target.value)} />
              </Campo>
            )}
            <Campo etiqueta="Descripción" className={modo === 'libre' ? '' : 'sm:col-span-2'}>
              <input value={descripcion} maxLength={600} onChange={(e) => setDescripcion(e.target.value)} />
            </Campo>
            <Campo etiqueta="Cantidad">
              <input inputMode="decimal" value={cantidad} onChange={(e) => setCantidad(e.target.value)} />
            </Campo>
            <Campo etiqueta="Precio unitario (pesos)" ayuda={articulo && articulo.precios.length > 1 ? 'Del catálogo; puedes cambiarlo.' : undefined}>
              <input inputMode="decimal" value={precio} placeholder="0.00" onChange={(e) => setPrecio(e.target.value)} />
            </Campo>
            <SelectorSeccion secciones={secciones} valor={seccion} alCambiar={setSeccion} />
            {valorCantidad !== null && valorPrecio !== null && (
              <p className="self-end pb-3 text-sm text-texto-secundario">
                Importe: <span className="tabular-nums text-texto">{moneda(valorCantidad * valorPrecio)}</span>
              </p>
            )}
          </div>
        )}

        <p className="text-xs text-texto-secundario">{AVISO_SISTEMA}</p>
        {agregar.isError && <Aviso tono="error">{mensajeDeError(agregar.error)}</Aviso>}
        <div className="flex justify-end gap-2 border-t border-borde pt-4">
          <Boton variante="fantasma" onClick={alCerrar}>
            Cancelar
          </Boton>
          <Boton icono={<Plus className="h-4 w-4" />} disabled={!listo} cargando={agregar.isPending} onClick={guardar}>
            Agregar
          </Boton>
        </div>
      </div>
    </Modal>
  )
}

// ---------------------------------------------------------------------------
// Editar
// ---------------------------------------------------------------------------

/** Cantidad, precio y sección de una partida, sólo en ProVista; también la quita de la cotización. */
export function EditarPartida({
  cotizacionId,
  item,
  secciones,
  alCerrar,
}: {
  cotizacionId: string
  item: CotizacionItem
  secciones: string[]
  alCerrar: () => void
}) {
  const editar = useEditarPartida(cotizacionId)
  const quitar = useQuitarPartida(cotizacionId)
  const [cantidad, setCantidad] = useState(String(item.cantidad))
  const [precio, setPrecio] = useState(String(item.precio_unitario))
  const [seccion, setSeccion] = useState(item.categoria)
  const [confirmarQuitar, setConfirmarQuitar] = useState(false)

  const valorCantidad = numero(cantidad)
  const valorPrecio = numero(precio)
  const valido = valorCantidad !== null && valorCantidad > 0 && valorPrecio !== null && valorPrecio >= 0
  const cambios = valido && (valorCantidad !== item.cantidad || valorPrecio !== item.precio_unitario || seccion.trim() !== item.categoria)
  const delSistema = item.origen === 'sistema'
  const cantidadSistema = item.cantidad_sistema ?? item.cantidad
  const precioSistema = item.precio_sistema ?? item.precio_unitario
  const error = editar.error ?? quitar.error

  return (
    <Modal abierto titulo="Editar partida" subtitulo={`${item.codigo_origen || 'Sin código'} · ${item.descripcion_origen}`} alCerrar={alCerrar}>
      <div className="flex flex-col gap-4">
        {delSistema ? (
          <p className="text-sm text-texto-secundario">
            En el sistema principal: {formatoCantidad(cantidadSistema)} × {moneda(precioSistema)} en {item.categoria_sistema || 'sin sección'}.
          </p>
        ) : (
          <p className="text-sm text-texto-secundario">Partida agregada en ProVista (no está en el sistema principal).</p>
        )}
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo etiqueta="Cantidad">
            <input autoFocus inputMode="decimal" value={cantidad} onChange={(e) => setCantidad(e.target.value)} />
          </Campo>
          <Campo etiqueta="Precio unitario (pesos)">
            <input inputMode="decimal" value={precio} onChange={(e) => setPrecio(e.target.value)} />
          </Campo>
          <SelectorSeccion secciones={secciones} valor={seccion} alCambiar={setSeccion} />
          {valido && (
            <p className="self-end pb-3 text-sm text-texto-secundario">
              Importe: <span className="tabular-nums text-texto">{moneda((valorCantidad as number) * (valorPrecio as number))}</span>
            </p>
          )}
        </div>
        <p className="text-xs text-texto-secundario">{AVISO_SISTEMA}</p>
        {error && <Aviso tono="error">{mensajeDeError(error)}</Aviso>}
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-borde pt-4">
          {confirmarQuitar ? (
            <span className="flex flex-wrap items-center gap-2 text-sm">
              {delSistema ? '¿Quitarla? Podrás restaurarla desde el aviso.' : '¿Quitarla? Se borra porque no está en el sistema.'}
              <Boton cargando={quitar.isPending} onClick={() => quitar.mutate(item.id, { onSuccess: alCerrar })}>
                Sí, quitar
              </Boton>
              <Boton variante="fantasma" onClick={() => setConfirmarQuitar(false)}>
                No
              </Boton>
            </span>
          ) : (
            <Boton variante="fantasma" icono={<Trash2 className="h-4 w-4" />} onClick={() => setConfirmarQuitar(true)}>
              Quitar de la cotización
            </Boton>
          )}
          <div className="flex gap-2">
            <Boton variante="fantasma" onClick={alCerrar}>
              Cancelar
            </Boton>
            <Boton
              disabled={!cambios}
              cargando={editar.isPending}
              onClick={() =>
                editar.mutate(
                  {
                    itemId: item.id,
                    cambios: {
                      ...(valorCantidad !== item.cantidad ? { cantidad: valorCantidad as number } : {}),
                      ...(valorPrecio !== item.precio_unitario ? { precio_unitario: valorPrecio as number } : {}),
                      ...(seccion.trim() !== item.categoria ? { categoria: seccion } : {}),
                    },
                  },
                  { onSuccess: alCerrar },
                )
              }
            >
              Guardar
            </Boton>
          </div>
        </div>
      </div>
    </Modal>
  )
}
