import { Check, Sparkles, Upload } from 'lucide-react'
import { useMemo, useRef, useState } from 'react'

import { useAsignarImagen, useGenerarImagenes, useImagenesDeItem, useSubirImagen } from '@/api/consultas'
import type { CotizacionItem, Imagen } from '@/api/tipos'
import { Aviso, mensajeDeError } from '@/componentes/Aviso'
import { Boton } from '@/componentes/Boton'
import { Miniatura } from '@/componentes/Miniatura'
import { Modal } from '@/componentes/Modal'
import { PildoraTipoImagen } from '@/componentes/Pildora'

type Pestana = 'biblioteca' | 'generar'

const ATAJOS_ACABADOS = [
  'Madera nogal',
  'Madera encino claro',
  'Blanco mate',
  'Negro mate',
  'Dorado cepillado',
  'Ratán natural',
  'Terciopelo verde',
  'Lino crudo',
]

interface Props {
  item: CotizacionItem
  cotizacionId: string
  alCerrar: () => void
}

export function SelectorImagen({ item, cotizacionId, alCerrar }: Props) {
  const esAdHoc = item.tipo_item === 'ad_hoc' || !item.item_id
  const [pestana, setPestana] = useState<Pestana>('biblioteca')
  const asignar = useAsignarImagen(cotizacionId)

  const elegir = (imagenId: string | null) => {
    asignar.mutate({ itemId: item.id, imagenId }, { onSuccess: alCerrar })
  }

  return (
    <Modal abierto titulo="Elegir imagen" subtitulo={`${item.codigo_origen || 'Sin código'} · ${item.descripcion_origen}`} alCerrar={alCerrar}>
      {!esAdHoc && (
        <div className="mb-5 flex gap-1 border-b border-borde" role="tablist">
          {(
            [
              ['biblioteca', 'Biblioteca'],
              ['generar', 'Generar imagen'],
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
      )}

      {asignar.isError && (
        <Aviso tono="error" className="mb-4">
          {mensajeDeError(asignar.error)}
        </Aviso>
      )}

      {pestana === 'biblioteca' || esAdHoc ? (
        <PestanaBiblioteca item={item} esAdHoc={esAdHoc} alElegir={elegir} ocupado={asignar.isPending} />
      ) : (
        <PestanaGenerar item={item} alElegir={elegir} ocupado={asignar.isPending} />
      )}
    </Modal>
  )
}

// ---------------------------------------------------------------------------
// Pestaña Biblioteca
// ---------------------------------------------------------------------------

function BotonSubir({ item, alSubida, etiqueta = 'Subir imagen nueva' }: { item: CotizacionItem; alSubida: (imagen: Imagen) => void; etiqueta?: string }) {
  const entrada = useRef<HTMLInputElement>(null)
  const subir = useSubirImagen()

  return (
    <>
      <Boton variante="secundario" icono={<Upload className="h-4 w-4" />} cargando={subir.isPending} onClick={() => entrada.current?.click()}>
        {etiqueta}
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
          subir.mutate({ archivo, itemId: item.item_id, tipo: 'variante' }, { onSuccess: alSubida })
        }}
      />
      {subir.isError && (
        <Aviso tono="error" className="mt-3">
          {mensajeDeError(subir.error)}
        </Aviso>
      )}
    </>
  )
}

function PestanaBiblioteca({
  item,
  esAdHoc,
  alElegir,
  ocupado,
}: {
  item: CotizacionItem
  esAdHoc: boolean
  alElegir: (imagenId: string | null) => void
  ocupado: boolean
}) {
  const imagenes = useImagenesDeItem(esAdHoc ? null : item.item_id)
  const [etiqueta, setEtiqueta] = useState<string | null>(null)

  const etiquetas = useMemo(() => {
    const todas = new Set<string>()
    imagenes.data?.forEach((imagen) => imagen.etiquetas.forEach((e) => todas.add(e)))
    return [...todas].sort()
  }, [imagenes.data])

  const visibles = useMemo(
    () => (imagenes.data ?? []).filter((imagen) => !etiqueta || imagen.etiquetas.includes(etiqueta)),
    [imagenes.data, etiqueta],
  )

  if (esAdHoc) {
    return (
      <div className="flex flex-col gap-4">
        <Aviso tono="info">
          Este ítem no está en el catálogo, así que no tiene biblioteca ni imagen base para generar. Sube una foto para
          usarla en esta propuesta.
        </Aviso>
        {item.imagen && (
          <div className="flex items-center gap-4">
            <Miniatura url={item.imagen.url} tamano="md" />
            <p className="text-sm text-texto-secundario">Imagen actual</p>
          </div>
        )}
        <div className="flex flex-wrap items-center gap-3">
          <BotonSubir item={item} alSubida={(imagen) => alElegir(imagen.id)} etiqueta="Subir foto" />
          {item.imagen && (
            <Boton variante="fantasma" onClick={() => alElegir(null)} disabled={ocupado}>
              Quitar imagen
            </Boton>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          <ChipFiltro activo={etiqueta === null} onClick={() => setEtiqueta(null)}>
            Todas
          </ChipFiltro>
          {etiquetas.map((e) => (
            <ChipFiltro key={e} activo={etiqueta === e} onClick={() => setEtiqueta(e)}>
              {e}
            </ChipFiltro>
          ))}
        </div>
        <BotonSubir item={item} alSubida={(imagen) => alElegir(imagen.id)} />
      </div>

      {imagenes.isLoading && <p className="text-sm text-texto-secundario">Cargando biblioteca…</p>}
      {imagenes.isError && <Aviso tono="error">{mensajeDeError(imagenes.error)}</Aviso>}
      {imagenes.data?.length === 0 && (
        <Aviso tono="ambar">Este ítem todavía no tiene imágenes en la biblioteca. Sube la primera.</Aviso>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
        {visibles.map((imagen) => {
          const seleccionada = imagen.id === item.imagen_id
          return (
            <button
              key={imagen.id}
              type="button"
              disabled={ocupado}
              onClick={() => alElegir(imagen.id)}
              className={`group flex flex-col gap-2 rounded-tarjeta border p-2 text-left transition-colors hover:border-acento ${
                seleccionada ? 'border-acento bg-acento-suave/40' : 'border-borde bg-superficie'
              }`}
            >
              <div className="relative">
                <Miniatura url={imagen.url} tamano="lg" conceptual={imagen.tipo === 'generada'} className="h-auto w-full aspect-square" />
                {seleccionada && (
                  <span className="absolute right-1 top-1 flex h-6 w-6 items-center justify-center rounded-full bg-acento text-superficie">
                    <Check className="h-3.5 w-3.5" />
                  </span>
                )}
              </div>
              <div className="flex items-center justify-between gap-2">
                <PildoraTipoImagen tipo={imagen.tipo} />
                <span className="text-xs text-texto-secundario">{imagen.usos} usos</span>
              </div>
            </button>
          )
        })}
      </div>

      {item.imagen && (
        <div className="border-t border-borde pt-3">
          <Boton variante="fantasma" onClick={() => alElegir(null)} disabled={ocupado}>
            Quitar imagen de este ítem
          </Boton>
        </div>
      )}
    </div>
  )
}

function ChipFiltro({ activo, onClick, children }: { activo: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-pildora border px-3 py-1 text-xs font-medium ${
        activo ? 'border-texto bg-texto text-superficie' : 'border-borde text-texto-secundario hover:text-texto'
      }`}
    >
      {children}
    </button>
  )
}

// ---------------------------------------------------------------------------
// Pestaña Generar imagen
// ---------------------------------------------------------------------------

function PestanaGenerar({ item, alElegir, ocupado }: { item: CotizacionItem; alElegir: (imagenId: string) => void; ocupado: boolean }) {
  const imagenes = useImagenesDeItem(item.item_id)
  const generar = useGenerarImagenes()
  const [peticion, setPeticion] = useState('')

  const base = useMemo(() => {
    const lista = imagenes.data ?? []
    return lista.find((i) => i.tipo === 'oficial') ?? lista.find((i) => i.tipo === 'variante') ?? null
  }, [imagenes.data])

  const agregarAtajo = (texto: string) => {
    setPeticion((actual) => (actual.trim() ? `${actual.trim()}, ${texto.toLowerCase()}` : texto))
  }

  const lanzar = () => {
    if (!base || !item.item_id) return
    generar.mutate({ item_id: item.item_id, imagen_base_id: base.id, peticion: peticion.trim() })
  }

  if (imagenes.isLoading) return <p className="text-sm text-texto-secundario">Cargando imagen base…</p>
  if (!base) {
    return (
      <Aviso tono="ambar">
        Este ítem no tiene imagen oficial en la biblioteca, así que no hay base para generar. Sube una en la pestaña
        Biblioteca y vuelve aquí.
      </Aviso>
    )
  }

  const resultados = generar.data?.imagenes ?? []

  return (
    <div className="grid gap-6 md:grid-cols-[200px_1fr]">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-texto-secundario">Imagen base</p>
        <Miniatura url={base.url} tamano="lg" className="mt-2 h-auto w-full aspect-square" />
        <p className="mt-2 text-xs text-texto-secundario">Foto {base.tipo} del ítem {item.item?.codigo ?? item.codigo_origen}.</p>
      </div>

      <div className="flex flex-col gap-4">
        <label className="flex flex-col gap-1.5 text-sm font-medium">
          Qué pidió el cliente
          <textarea
            rows={3}
            value={peticion}
            maxLength={600}
            placeholder="Ej. la misma silla pero en madera de nogal con asiento de lino crudo"
            onChange={(evento) => setPeticion(evento.target.value)}
          />
        </label>

        <div>
          <p className="mb-2 text-xs text-texto-secundario">Acabados frecuentes</p>
          <div className="flex flex-wrap gap-2">
            {ATAJOS_ACABADOS.map((atajo) => (
              <ChipFiltro key={atajo} activo={false} onClick={() => agregarAtajo(atajo)}>
                {atajo}
              </ChipFiltro>
            ))}
          </div>
        </div>

        <Aviso tono="info">
          El ángulo (tres cuartos), el fondo neutro y la iluminación los fija el sistema. Describe sólo el acabado, material
          o color; la forma de la pieza se conserva.
        </Aviso>

        <div>
          <Boton icono={<Sparkles className="h-4 w-4" />} cargando={generar.isPending} disabled={peticion.trim().length < 3} onClick={lanzar}>
            Generar 4 opciones
          </Boton>
          {generar.isPending && <p className="mt-2 text-xs text-texto-secundario">Esto tarda entre 30 y 90 segundos.</p>}
        </div>

        {generar.isError && <Aviso tono="error">{mensajeDeError(generar.error)}</Aviso>}

        {resultados.length > 0 && (
          <div className="flex flex-col gap-3">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {resultados.map((imagen, indice) => (
                <button
                  key={imagen.id}
                  type="button"
                  disabled={ocupado}
                  onClick={() => alElegir(imagen.id)}
                  className="group flex flex-col gap-1.5 rounded-tarjeta border border-borde p-2 text-left hover:border-acento"
                >
                  <Miniatura url={imagen.url} tamano="lg" conceptual className="h-auto w-full aspect-square" />
                  <span className="text-xs font-medium text-texto-secundario group-hover:text-texto">Usar opción {indice + 1}</span>
                </button>
              ))}
            </div>
            <Aviso tono="ambar">
              Estas imágenes son una referencia del acabado, sujeta a confirmación de producción. En el PDF llevan la
              etiqueta "Render conceptual" y una leyenda al pie.
            </Aviso>
          </div>
        )}
      </div>
    </div>
  )
}
