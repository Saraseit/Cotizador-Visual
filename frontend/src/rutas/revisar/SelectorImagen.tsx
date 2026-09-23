import { Check, Upload } from 'lucide-react'
import { useMemo, useRef, useState } from 'react'

import { useAsignarImagen, useImagenesDeItem, useSubirImagen } from '@/api/consultas'
import type { CotizacionItem, Imagen } from '@/api/tipos'
import { Aviso, mensajeDeError } from '@/componentes/Aviso'
import { Boton } from '@/componentes/Boton'
import { Chip } from '@/componentes/Campo'
import { Miniatura } from '@/componentes/Miniatura'
import { Modal } from '@/componentes/Modal'
import { PanelGenerar } from '@/componentes/PanelGenerar'
import { PildoraTipoImagen } from '@/componentes/Pildora'

type Pestana = 'biblioteca' | 'generar'

interface Props {
  item: CotizacionItem
  cotizacionId: string
  alCerrar: () => void
}

export function SelectorImagen({ item, cotizacionId, alCerrar }: Props) {
  const esAdHoc = item.tipo_item === 'ad_hoc' || !item.item_id
  const [pestana, setPestana] = useState<Pestana>('biblioteca')
  const asignar = useAsignarImagen(cotizacionId)

  /** Asigna la imagen al ítem. Por defecto cierra la ventana; con `cerrar=false` se queda abierta. */
  const elegir = (imagenId: string | null, cerrar = true) => {
    asignar.mutate({ itemId: item.id, imagenId }, { onSuccess: () => cerrar && alCerrar() })
  }

  return (
    <Modal
      abierto
      titulo="Elegir imagen"
      subtitulo={`${item.codigo_origen || 'Sin código'} · ${item.descripcion_origen}`}
      alCerrar={alCerrar}
    >
      <div className="mb-5 flex gap-1 border-b border-borde" role="tablist">
        {(
          [
            ['biblioteca', esAdHoc ? 'Subir foto' : 'Biblioteca'],
            ['generar', 'Generar imagen con IA'],
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

      {asignar.isError && (
        <Aviso tono="error" className="mb-4">
          {mensajeDeError(asignar.error)}
        </Aviso>
      )}

      {pestana === 'biblioteca' ? (
        <PestanaBiblioteca item={item} esAdHoc={esAdHoc} alElegir={elegir} ocupado={asignar.isPending} />
      ) : (
        <PestanaGenerar item={item} esAdHoc={esAdHoc} cotizacionId={cotizacionId} alElegir={elegir} ocupado={asignar.isPending} />
      )}
    </Modal>
  )
}

// ---------------------------------------------------------------------------
// Subir
// ---------------------------------------------------------------------------

function BotonSubir({
  item,
  alSubida,
  etiqueta = 'Subir imagen nueva',
}: {
  item: CotizacionItem
  alSubida: (imagen: Imagen) => void
  etiqueta?: string
}) {
  const entrada = useRef<HTMLInputElement>(null)
  const subir = useSubirImagen()

  return (
    <>
      <Boton
        variante="secundario"
        icono={<Upload className="h-4 w-4" />}
        cargando={subir.isPending}
        onClick={() => entrada.current?.click()}
      >
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

// ---------------------------------------------------------------------------
// Pestaña Biblioteca
// ---------------------------------------------------------------------------

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
          Este ítem no está en el catálogo, así que no tiene biblioteca. Sube una foto para usarla en esta propuesta; después puedes generar
          variantes con IA a partir de ella en la otra pestaña.
        </Aviso>
        {item.imagen && (
          <div className="flex items-center gap-4">
            <Miniatura url={item.imagen.url} tamano="md" conceptual={item.es_render_conceptual} />
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
          <Chip activo={etiqueta === null} onClick={() => setEtiqueta(null)}>
            Todas
          </Chip>
          {etiquetas.map((e) => (
            <Chip key={e} activo={etiqueta === e} onClick={() => setEtiqueta(e)}>
              {e}
            </Chip>
          ))}
        </div>
        <BotonSubir item={item} alSubida={(imagen) => alElegir(imagen.id)} />
      </div>

      {imagenes.isLoading && <p className="text-sm text-texto-secundario">Cargando biblioteca…</p>}
      {imagenes.isError && <Aviso tono="error">{mensajeDeError(imagenes.error)}</Aviso>}
      {imagenes.data?.length === 0 && <Aviso tono="ambar">Este ítem todavía no tiene imágenes en la biblioteca. Sube la primera.</Aviso>}

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

// ---------------------------------------------------------------------------
// Pestaña Generar
// ---------------------------------------------------------------------------

function PestanaGenerar({
  item,
  esAdHoc,
  cotizacionId,
  alElegir,
  ocupado,
}: {
  item: CotizacionItem
  esAdHoc: boolean
  cotizacionId: string
  alElegir: (imagenId: string | null, cerrar?: boolean) => void
  ocupado: boolean
}) {
  const imagenes = useImagenesDeItem(esAdHoc ? null : item.item_id)

  // Base: la oficial del catálogo; si no hay, una variante; si no, la imagen ya asignada al ítem.
  const base = useMemo<Imagen | null>(() => {
    const lista = imagenes.data ?? []
    return (
      lista.find((i) => i.tipo === 'oficial') ??
      lista.find((i) => i.tipo === 'variante') ??
      (item.imagen && item.imagen.tipo !== 'generada' ? item.imagen : null) ??
      item.imagen ??
      null
    )
  }, [imagenes.data, item.imagen])

  if (!esAdHoc && imagenes.isLoading) return <p className="text-sm text-texto-secundario">Cargando imagen base…</p>

  return (
    <PanelGenerar
      imagenBase={base}
      itemId={item.item_id}
      cotizacionId={cotizacionId}
      etiquetaBase={base ? `Base: ${base.tipo} de ${item.item?.codigo ?? (item.codigo_origen || 'este ítem')}` : undefined}
      alElegir={(imagenId) => alElegir(imagenId)}
      ocupado={ocupado}
      sinBase={
        <div className="flex flex-col gap-4">
          <Aviso tono="ambar">
            {esAdHoc
              ? 'Este ítem no tiene foto todavía. Sube una y se usará como base para generar las variantes.'
              : 'Este ítem no tiene imagen en la biblioteca. Sube una foto (queda como variante) y se usará como base.'}
          </Aviso>
          <div>
            <BotonSubir item={item} alSubida={(imagen) => alElegir(imagen.id, false)} etiqueta="Subir foto base" />
          </div>
        </div>
      }
    />
  )
}
