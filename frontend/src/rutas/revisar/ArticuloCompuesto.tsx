import { useQueryClient } from '@tanstack/react-query'
import { Check, Combine, ImagePlus, Sparkles, Split, Upload } from 'lucide-react'
import { useRef, useState, type ReactNode } from 'react'

import { ErrorApi, api } from '@/api/cliente'
import {
  llaves,
  useCrearCompuesto,
  useEditarCompuesto,
  useGenerarImagenCompuesto,
  useSepararCompuesto,
  useSubirImagen,
} from '@/api/consultas'
import type { Compuesto, CotizacionItem, PrecioCompuesto, PrecioModo } from '@/api/tipos'
import { Aviso, mensajeDeError } from '@/componentes/Aviso'
import { Boton } from '@/componentes/Boton'
import { Campo } from '@/componentes/Campo'
import { Miniatura } from '@/componentes/Miniatura'
import { Modal } from '@/componentes/Modal'
import { cantidad } from '@/lib/formato'

/** Cómo se consigue la foto del artículo completo. */
export type PestanaCompuesto = 'fotos' | 'subir' | 'generar'

const descripcion = (item: CotizacionItem) => item.descripcion_editada.trim() || item.descripcion_origen

/** Lo mismo que propone el backend si el vendedor no escribe un nombre. */
const nombrePorDefecto = (partidas: CotizacionItem[]) =>
  partidas
    .map(descripcion)
    .filter((d) => d.trim())
    .join(' + ')
    .slice(0, 200)

/** SKUs de catálogo del compuesto: a sus galerías va la foto nueva del artículo completo. */
const skus = (partidas: CotizacionItem[]) =>
  partidas.filter((p) => p.item_id).map((p) => p.item?.codigo || p.codigo_origen || 'sin código')

function ListaPartidas({ partidas, dinero }: { partidas: CotizacionItem[]; dinero: (valor: number) => string }) {
  return (
    <ul className="divide-y divide-borde rounded-tarjeta border border-borde text-sm">
      {partidas.map((p) => (
        <li key={p.id} className="flex items-center gap-3 px-3 py-2">
          <Miniatura url={p.imagen?.url} alt={p.descripcion_origen} />
          <div className="min-w-0 flex-1">
            <p className="truncate">{descripcion(p)}</p>
            <p className="text-xs text-texto-secundario">{p.codigo_origen || 'Sin código'}</p>
          </div>
          <span className="whitespace-nowrap tabular-nums text-texto-secundario">
            {cantidad(p.cantidad)} × {dinero(p.precio_unitario)}
          </span>
        </li>
      ))}
    </ul>
  )
}

function TarjetaOpcion({
  activa,
  onClick,
  disabled,
  children,
}: {
  activa: boolean
  onClick: () => void
  disabled?: boolean
  children: ReactNode
}) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={activa}
      disabled={disabled}
      onClick={onClick}
      className={`relative flex flex-col gap-2 rounded-tarjeta border p-2 text-left text-xs transition-colors hover:border-acento disabled:opacity-60 ${
        activa ? 'border-acento bg-acento-suave/40' : 'border-borde bg-superficie'
      }`}
    >
      {children}
      {activa && (
        <span className="absolute right-1 top-1 flex h-6 w-6 items-center justify-center rounded-full bg-acento text-superficie">
          <Check className="h-3.5 w-3.5" />
        </span>
      )}
    </button>
  )
}

// ---------------------------------------------------------------------------
// Precio
// ---------------------------------------------------------------------------

/** Lo que se edita: el modo, la partida elegida y el precio manual tal como se escribe. */
interface EstadoPrecio {
  modo: PrecioModo
  itemId: string | null
  manual: string
}

const estadoDe = (compuesto?: Compuesto): EstadoPrecio => ({
  modo: compuesto?.precio_modo ?? 'suma',
  itemId: compuesto?.precio_item_id ?? null,
  manual: compuesto?.precio_manual != null ? String(compuesto.precio_manual) : '',
})

const precioManual = (texto: string) => {
  const valor = Number(texto.replace(/[$,\s]/g, ''))
  return texto.trim() && Number.isFinite(valor) && valor >= 0 ? valor : null
}

/** Para mandar al backend; null si falta el dato del modo elegido. */
function precioDe(estado: EstadoPrecio): PrecioCompuesto | null {
  if (estado.modo === 'partida') return estado.itemId ? { precio_modo: 'partida', precio_item_id: estado.itemId } : null
  if (estado.modo === 'manual') {
    const valor = precioManual(estado.manual)
    return valor === null ? null : { precio_modo: 'manual', precio_manual: valor }
  }
  return { precio_modo: 'suma' }
}

/** Mismo cálculo que el backend (`servicios/compuestos.Renglon`): cantidad e importe que se presentan. */
function calcular(estado: EstadoPrecio, partidas: CotizacionItem[]) {
  const suma = partidas.reduce((total, p) => total + p.importe, 0)
  const cantidades = new Set(partidas.map((p) => p.cantidad))
  const comun = cantidades.size === 1 ? partidas[0].cantidad : null
  if (estado.modo === 'partida') {
    const partida = partidas.find((p) => p.id === estado.itemId)
    if (partida) return { suma, cantidad: partida.cantidad, unitario: partida.precio_unitario, importe: partida.cantidad * partida.precio_unitario }
  }
  if (estado.modo === 'manual') {
    const valor = precioManual(estado.manual)
    const cantidadArticulos = comun ?? partidas[0].cantidad
    if (valor !== null) return { suma, cantidad: cantidadArticulos, unitario: valor, importe: cantidadArticulos * valor }
    return { suma, cantidad: cantidadArticulos, unitario: null, importe: null }
  }
  const unitario = comun !== null ? partidas.reduce((total, p) => total + p.precio_unitario, 0) : null
  return { suma, cantidad: comun, unitario, importe: suma }
}

function OpcionPrecio({ activa, onClick, children }: { activa: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <label className={`flex cursor-pointer items-start gap-3 rounded-boton border px-3 py-2 text-sm ${activa ? 'border-acento bg-acento-suave/40' : 'border-borde'}`}>
      <input type="radio" className="mt-1 accent-acento" checked={activa} onChange={onClick} />
      <div className="min-w-0 flex-1">{children}</div>
    </label>
  )
}

/**
 * Qué precio presenta el compuesto: la suma de sus partidas (cuadra con el PDF del sistema), el de una
 * de ellas o uno escrito por el vendedor. Las partidas en sí no cambian.
 */
function SelectorPrecio({
  partidas,
  estado,
  alCambiar,
  dinero,
}: {
  partidas: CotizacionItem[]
  estado: EstadoPrecio
  alCambiar: (estado: EstadoPrecio) => void
  dinero: (valor: number) => string
}) {
  const calculo = calcular(estado, partidas)
  const sumaUnitaria = calcular({ modo: 'suma', itemId: null, manual: '' }, partidas).unitario
  const diferencia = calculo.importe !== null ? calculo.importe - calculo.suma : 0

  return (
    <div>
      <p className="text-sm font-medium">Precio del artículo</p>
      <div className="mt-2 flex flex-col gap-2" role="radiogroup" aria-label="Precio del artículo">
        <OpcionPrecio activa={estado.modo === 'suma'} onClick={() => alCambiar({ ...estado, modo: 'suma' })}>
          <span>Suma de las partidas</span>
          <span className="ml-2 tabular-nums text-texto-secundario">
            {sumaUnitaria !== null && `${dinero(sumaUnitaria)} c/u · `}
            {dinero(calculo.suma)}
          </span>
          <p className="text-xs text-texto-secundario">Cuadra con el PDF del sistema.</p>
        </OpcionPrecio>
        {partidas.map((p) => (
          <OpcionPrecio
            key={p.id}
            activa={estado.modo === 'partida' && estado.itemId === p.id}
            onClick={() => alCambiar({ ...estado, modo: 'partida', itemId: p.id })}
          >
            <span>Sólo el precio de {descripcion(p)}</span>
            <span className="ml-2 tabular-nums text-texto-secundario">
              {dinero(p.precio_unitario)} c/u · {cantidad(p.cantidad)} = {dinero(p.importe)}
            </span>
          </OpcionPrecio>
        ))}
        <OpcionPrecio activa={estado.modo === 'manual'} onClick={() => alCambiar({ ...estado, modo: 'manual' })}>
          <span>Otro precio por artículo</span>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <input
              inputMode="decimal"
              className="w-36"
              placeholder="0.00"
              aria-label="Precio por artículo en pesos"
              value={estado.manual}
              onFocus={() => estado.modo !== 'manual' && alCambiar({ ...estado, modo: 'manual' })}
              onChange={(e) => alCambiar({ ...estado, modo: 'manual', manual: e.target.value })}
            />
            <span className="text-xs text-texto-secundario">
              pesos por artículo
              {estado.modo === 'manual' && calculo.importe !== null && ` · ${cantidad(calculo.cantidad ?? 0)} = ${dinero(calculo.importe)}`}
            </span>
          </div>
        </OpcionPrecio>
      </div>
      {estado.modo !== 'suma' && calculo.importe !== null && Math.abs(diferencia) >= 0.005 && (
        <p className="mt-2 text-xs font-medium text-alerta-texto">
          Con este precio la propuesta deja de cuadrar con el PDF del sistema ({diferencia > 0 ? '+' : '−'}
          {dinero(Math.abs(diferencia))} antes de IVA).
        </p>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Combinar
// ---------------------------------------------------------------------------

type Eleccion = { tipo: 'partida'; imagenId: string } | { tipo: 'subir' } | { tipo: 'generar' }

interface PropsCombinar {
  cotizacionId: string
  /** Partidas marcadas, en el orden de impresión. */
  partidas: CotizacionItem[]
  dinero: (valor: number) => string
  alCerrar: () => void
  /** Ya combinadas. Si la foto se va a subir o generar, `siguiente` dice en qué pestaña abrir el editor. */
  alCombinar: (compuestoId: string, siguiente: PestanaCompuesto | null) => void
}

/** Combina las partidas marcadas en un artículo compuesto (sólo presentación: precios iguales). */
export function CombinarArticulos({ cotizacionId, partidas, dinero, alCerrar, alCombinar }: PropsCombinar) {
  const crear = useCrearCompuesto(cotizacionId)
  const conFoto = partidas.filter((p) => p.imagen)
  const [nombre, setNombre] = useState('')
  const [precio, setPrecio] = useState<EstadoPrecio>(estadoDe())
  const precioListo = precioDe(precio)
  const [eleccion, setEleccion] = useState<Eleccion>(
    conFoto[0]?.imagen_id ? { tipo: 'partida', imagenId: conFoto[0].imagen_id } : { tipo: 'subir' },
  )
  const galerias = skus(partidas)

  const combinar = () => {
    crear.mutate(
      {
        item_ids: partidas.map((p) => p.id),
        nombre: nombre.trim(),
        imagen_id: eleccion.tipo === 'partida' ? eleccion.imagenId : null,
        precio: precioListo ?? { precio_modo: 'suma' },
      },
      {
        onSuccess: (detalle) => {
          const nuevo = detalle.compuestos.find((c) => c.item_ids.includes(partidas[0].id))
          if (nuevo) alCombinar(nuevo.id, eleccion.tipo === 'partida' ? null : eleccion.tipo)
          else alCerrar()
        },
      },
    )
  }

  return (
    <Modal abierto titulo="Combinar en un artículo" subtitulo={`${partidas.length} partidas`} alCerrar={alCerrar}>
      <div className="flex flex-col gap-5">
        <Aviso tono="info">
          En la propuesta saldrán como un solo artículo, con una foto y este nombre, y debajo cada partida con su código. Por defecto el
          precio es la suma de las partidas; puedes dejar sólo el de una o escribir otro.
        </Aviso>

        <ListaPartidas partidas={partidas} dinero={dinero} />

        <Campo etiqueta="Nombre del artículo" ayuda="Vacío = las descripciones de las partidas unidas.">
          <input value={nombre} maxLength={200} placeholder={nombrePorDefecto(partidas)} onChange={(e) => setNombre(e.target.value)} />
        </Campo>

        <SelectorPrecio partidas={partidas} estado={precio} alCambiar={setPrecio} dinero={dinero} />

        <div>
          <p className="text-sm font-medium">Foto del artículo</p>
          <div className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-4" role="radiogroup" aria-label="Foto del artículo">
            {conFoto.map((p) => (
              <TarjetaOpcion
                key={p.id}
                activa={eleccion.tipo === 'partida' && eleccion.imagenId === p.imagen_id}
                onClick={() => p.imagen_id && setEleccion({ tipo: 'partida', imagenId: p.imagen_id })}
              >
                <Miniatura url={p.imagen?.url} tamano="lg" conceptual={p.es_render_conceptual} className="aspect-square h-auto w-full" />
                <span className="line-clamp-2 text-texto-secundario">Conservar la de {descripcion(p)}</span>
              </TarjetaOpcion>
            ))}
            <TarjetaOpcion activa={eleccion.tipo === 'subir'} onClick={() => setEleccion({ tipo: 'subir' })}>
              <div className="flex aspect-square w-full items-center justify-center rounded-boton bg-borde/40 text-texto-secundario">
                <Upload className="h-6 w-6" aria-hidden />
              </div>
              <span className="text-texto-secundario">Subir una foto del artículo completo</span>
            </TarjetaOpcion>
            <TarjetaOpcion activa={eleccion.tipo === 'generar'} onClick={() => setEleccion({ tipo: 'generar' })} disabled={!conFoto.length}>
              <div className="flex aspect-square w-full items-center justify-center rounded-boton bg-borde/40 text-texto-secundario">
                <Sparkles className="h-6 w-6" aria-hidden />
              </div>
              <span className="text-texto-secundario">
                {conFoto.length ? 'Generar con IA a partir de las fotos de las partidas' : 'Generar con IA (necesita fotos de las partidas)'}
              </span>
            </TarjetaOpcion>
          </div>
          {eleccion.tipo !== 'partida' && galerias.length > 0 && (
            <p className="mt-2 text-xs text-texto-secundario">La foto nueva se guarda también en la galería de {galerias.join(' y ')}.</p>
          )}
        </div>

        {crear.isError && <Aviso tono="error">{mensajeDeError(crear.error)}</Aviso>}

        <div className="flex flex-wrap justify-end gap-2 border-t border-borde pt-4">
          <Boton variante="fantasma" onClick={alCerrar} disabled={crear.isPending}>
            Cancelar
          </Boton>
          <Boton icono={<Combine className="h-4 w-4" />} cargando={crear.isPending} disabled={!precioListo} onClick={combinar}>
            {eleccion.tipo === 'partida' ? 'Combinar' : 'Combinar y elegir la foto'}
          </Boton>
        </div>
      </div>
    </Modal>
  )
}

// ---------------------------------------------------------------------------
// Editor del compuesto
// ---------------------------------------------------------------------------

interface PropsEditor {
  cotizacionId: string
  compuesto: Compuesto
  partidas: CotizacionItem[]
  dinero: (valor: number) => string
  pestanaInicial?: PestanaCompuesto
  alCerrar: () => void
}

/** Nombre y foto de un artículo compuesto; también lo separa. */
export function EditorCompuesto({ cotizacionId, compuesto, partidas, dinero, pestanaInicial = 'fotos', alCerrar }: PropsEditor) {
  const editar = useEditarCompuesto(cotizacionId)
  const separar = useSepararCompuesto(cotizacionId)
  const [pestana, setPestana] = useState<PestanaCompuesto>(pestanaInicial)
  const [nombre, setNombre] = useState(compuesto.nombre)
  const [precio, setPrecio] = useState<EstadoPrecio>(estadoDe(compuesto))
  const precioListo = precioDe(precio)
  const precioGuardado = estadoDe(compuesto)
  const precioCambiado =
    precio.modo !== precioGuardado.modo ||
    (precio.modo === 'partida' && precio.itemId !== precioGuardado.itemId) ||
    (precio.modo === 'manual' && precioManual(precio.manual) !== compuesto.precio_manual)
  const galerias = skus(partidas)

  /** Las fotos nuevas (subidas o generadas) van además a la galería de cada SKU. */
  const usarImagen = (imagenId: string | null, nueva: boolean, despues?: () => void) =>
    editar.mutate({ compuestoId: compuesto.id, imagen_id: imagenId, guardar_en_galerias: nueva }, { onSuccess: () => despues?.() })

  return (
    <Modal abierto titulo="Artículo compuesto" subtitulo={compuesto.nombre} alCerrar={alCerrar}>
      <div className="flex flex-col gap-5">
        <div className="grid gap-5 md:grid-cols-[180px_1fr]">
          <div>
            <Miniatura
              url={compuesto.imagen?.url}
              tamano="lg"
              conceptual={compuesto.imagen?.tipo === 'generada'}
              className="aspect-square h-auto w-full"
              alt={compuesto.nombre}
            />
            <p className="mt-1 text-xs text-texto-secundario">Foto que sale en la propuesta</p>
          </div>
          <div className="flex flex-col gap-3">
            <Campo etiqueta="Nombre del artículo" ayuda="Vacío = las descripciones de las partidas unidas.">
              <div className="flex gap-2">
                <input className="flex-1" value={nombre} maxLength={200} onChange={(e) => setNombre(e.target.value)} />
                <Boton
                  variante="secundario"
                  disabled={nombre === compuesto.nombre}
                  cargando={editar.isPending && editar.variables?.nombre !== undefined}
                  onClick={() => editar.mutate({ compuestoId: compuesto.id, nombre }, { onSuccess: (d) => setNombre(nombreDe(d.compuestos, compuesto)) })}
                >
                  Guardar
                </Boton>
              </div>
            </Campo>
            <ListaPartidas partidas={partidas} dinero={dinero} />
          </div>
        </div>

        <div className="rounded-tarjeta border border-borde p-4">
          <SelectorPrecio partidas={partidas} estado={precio} alCambiar={setPrecio} dinero={dinero} />
          <div className="mt-3 flex justify-end">
            <Boton
              variante="secundario"
              disabled={!precioCambiado || !precioListo}
              cargando={editar.isPending && editar.variables?.precio !== undefined}
              onClick={() => precioListo && editar.mutate({ compuestoId: compuesto.id, precio: precioListo })}
            >
              Guardar precio
            </Boton>
          </div>
        </div>

        <div className="flex gap-1 border-b border-borde" role="tablist">
          {(
            [
              ['fotos', 'Fotos de las partidas'],
              ['subir', 'Subir foto'],
              ['generar', 'Generar con IA'],
            ] as const
          ).map(([valor, texto]) => (
            <button
              key={valor}
              type="button"
              role="tab"
              aria-selected={pestana === valor}
              onClick={() => setPestana(valor)}
              className={`-mb-px min-h-boton border-b-2 px-4 text-sm font-medium ${
                pestana === valor ? 'border-acento text-texto' : 'border-transparent text-texto-secundario hover:text-texto'
              }`}
            >
              {texto}
            </button>
          ))}
        </div>

        {editar.isError && <Aviso tono="error">{mensajeDeError(editar.error)}</Aviso>}

        {pestana === 'fotos' && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4" role="radiogroup" aria-label="Foto del artículo">
            {partidas
              .filter((p) => p.imagen)
              .map((p) => (
                <TarjetaOpcion
                  key={p.id}
                  activa={compuesto.imagen_id === p.imagen_id}
                  disabled={editar.isPending}
                  onClick={() => usarImagen(p.imagen_id, false)}
                >
                  <Miniatura url={p.imagen?.url} tamano="lg" conceptual={p.es_render_conceptual} className="aspect-square h-auto w-full" />
                  <span className="line-clamp-2 text-texto-secundario">{descripcion(p)}</span>
                </TarjetaOpcion>
              ))}
            {!partidas.some((p) => p.imagen) && (
              <Aviso tono="ambar" className="col-span-full">
                Ninguna partida tiene foto. Sube una del artículo completo.
              </Aviso>
            )}
          </div>
        )}

        {pestana === 'subir' && (
          <PestanaSubir partidas={partidas} galerias={galerias} ocupado={editar.isPending} alSubida={(id) => usarImagen(id, true)} />
        )}

        {pestana === 'generar' && (
          <PestanaGenerar
            cotizacionId={cotizacionId}
            compuesto={compuesto}
            partidas={partidas}
            galerias={galerias}
            ocupado={editar.isPending}
            alElegir={(id, despues) => usarImagen(id, true, despues)}
          />
        )}

        {separar.isError && <Aviso tono="error">{mensajeDeError(separar.error)}</Aviso>}

        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-borde pt-4">
          <Boton
            variante="fantasma"
            icono={<Split className="h-4 w-4" />}
            cargando={separar.isPending}
            onClick={() => separar.mutate(compuesto.id, { onSuccess: alCerrar })}
            title="Las partidas vuelven a salir sueltas, cada una con su foto"
          >
            Separar partidas
          </Boton>
          <Boton variante="secundario" onClick={alCerrar}>
            Listo
          </Boton>
        </div>
      </div>
    </Modal>
  )
}

const nombreDe = (compuestos: Compuesto[], actual: Compuesto) => compuestos.find((c) => c.id === actual.id)?.nombre ?? actual.nombre

function PestanaSubir({
  partidas,
  galerias,
  ocupado,
  alSubida,
}: {
  partidas: CotizacionItem[]
  galerias: string[]
  ocupado: boolean
  alSubida: (imagenId: string) => void
}) {
  const entrada = useRef<HTMLInputElement>(null)
  const subir = useSubirImagen()
  // Se sube a la galería del primer SKU; al asignarla, el backend la copia a los demás.
  const duena = partidas.find((p) => p.item_id)?.item_id ?? null

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-texto-secundario">
        Una foto del artículo armado.{' '}
        {galerias.length > 0 ? `Se guarda en la galería de ${galerias.join(' y ')}.` : 'Las partidas no son de catálogo: queda sólo para esta propuesta.'}
      </p>
      <div>
        <Boton icono={<ImagePlus className="h-4 w-4" />} cargando={subir.isPending || ocupado} onClick={() => entrada.current?.click()}>
          Subir foto del artículo completo
        </Boton>
        <input
          ref={entrada}
          type="file"
          accept="image/png,image/jpeg,image/webp"
          className="hidden"
          onChange={(evento) => {
            const archivo = evento.target.files?.[0]
            evento.target.value = ''
            if (!archivo) return
            subir.mutate({ archivo, itemId: duena, tipo: 'variante', etiquetas: ['compuesto'] }, { onSuccess: (imagen) => alSubida(imagen.id) })
          }}
        />
      </div>
      {subir.isError && <Aviso tono="error">{mensajeDeError(subir.error)}</Aviso>}
    </div>
  )
}

function PestanaGenerar({
  cotizacionId,
  compuesto,
  partidas,
  galerias,
  ocupado,
  alElegir,
}: {
  cotizacionId: string
  compuesto: Compuesto
  partidas: CotizacionItem[]
  galerias: string[]
  ocupado: boolean
  alElegir: (imagenId: string, despues: () => void) => void
}) {
  const generar = useGenerarImagenCompuesto(cotizacionId)
  const clienteConsultas = useQueryClient()
  const [peticion, setPeticion] = useState('')
  const referencias = partidas.filter((p) => p.imagen)
  const resultados = generar.data?.imagenes ?? []
  const topeAlcanzado = generar.error instanceof ErrorApi && generar.error.estado === 429

  /** Al elegir una opción, las demás de la tanda se borran en segundo plano. */
  const elegir = (imagenId: string) => {
    const descartadas = resultados.filter((i) => i.id !== imagenId)
    alElegir(imagenId, () => {
      generar.reset()
      void Promise.allSettled(descartadas.map((i) => api.imagenes.eliminar(i.id))).then(() => {
        void clienteConsultas.invalidateQueries({ queryKey: ['catalogo', 'imagenes'] })
        void clienteConsultas.invalidateQueries({ queryKey: llaves.resumenBiblioteca })
      })
    })
  }

  if (!referencias.length) {
    return <Aviso tono="ambar">Ninguna partida tiene foto. Asigna al menos una para que la IA tenga de dónde partir.</Aviso>
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-texto-secundario">Fotos de base</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {referencias.map((p) => (
            <Miniatura key={p.id} url={p.imagen?.url} tamano="md" alt={p.descripcion_origen} />
          ))}
        </div>
      </div>
      <Campo etiqueta="Indicaciones (opcional)" ayuda="La IA arma el artículo completo con las piezas de las fotos. Puedes precisar cómo va montado.">
        <textarea
          rows={2}
          value={peticion}
          maxLength={600}
          placeholder="Ej. la cubierta centrada sobre la base, con mantel blanco hasta el piso"
          onChange={(e) => setPeticion(e.target.value)}
        />
      </Campo>
      <div>
        <Boton
          icono={<Sparkles className="h-4 w-4" />}
          cargando={generar.isPending}
          onClick={() => generar.mutate({ compuestoId: compuesto.id, peticion: peticion.trim() })}
        >
          Generar opciones
        </Boton>
        {generar.isPending && <p className="mt-2 text-xs text-texto-secundario">Esto tarda entre 30 y 90 segundos.</p>}
      </div>
      {generar.isError && <Aviso tono={topeAlcanzado ? 'ambar' : 'error'}>{mensajeDeError(generar.error)}</Aviso>}
      {resultados.length > 0 && (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {resultados.map((imagen, indice) => (
              <button
                key={imagen.id}
                type="button"
                disabled={ocupado}
                onClick={() => elegir(imagen.id)}
                className="group flex flex-col gap-1.5 rounded-tarjeta border border-borde p-2 text-left hover:border-acento"
              >
                <Miniatura url={imagen.url} tamano="lg" conceptual className="aspect-square h-auto w-full" />
                <span className="text-xs font-medium text-texto-secundario group-hover:text-texto">Usar opción {indice + 1}</span>
              </button>
            ))}
          </div>
          <Aviso tono="ambar">
            Render conceptual, sujeto a confirmación de producción: en el PDF lleva esa etiqueta.
            {galerias.length > 0 && ` La que elijas se guarda en la galería de ${galerias.join(' y ')}.`}
          </Aviso>
        </>
      )}
    </div>
  )
}
