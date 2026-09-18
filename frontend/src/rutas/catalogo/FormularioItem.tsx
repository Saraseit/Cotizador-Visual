import { Sparkles, Upload } from 'lucide-react'
import { useMemo, useRef, useState, type FormEvent } from 'react'

import { useActualizarItemCatalogo, useCrearItemCatalogo, useImagenesDeItem, useItemCatalogo, useSubirImagen } from '@/api/consultas'
import type { CatalogoItem, CatalogoItemEntrada, ListaPrecios } from '@/api/tipos'
import { Aviso, mensajeDeError } from '@/componentes/Aviso'
import { Boton } from '@/componentes/Boton'
import { Campo } from '@/componentes/Campo'
import { Miniatura } from '@/componentes/Miniatura'
import { Modal } from '@/componentes/Modal'
import { PanelGenerar } from '@/componentes/PanelGenerar'
import { PildoraTipoImagen } from '@/componentes/Pildora'

interface Props {
  /** null = crear uno nuevo */
  item: CatalogoItem | null
  listas: ListaPrecios[]
  alCerrar: () => void
  /** Tras crear, el formulario pasa a modo edición para poder subir fotos. */
  alCrear: (item: CatalogoItem) => void
}

interface Borrador {
  codigo: string
  nombre: string
  categoria: string
  descripcion: string
  medidas: string
  etiquetas: string
  costo_reposicion: string
  activo: boolean
  precios: Record<string, string>
}

function borradorDesde(item: CatalogoItem | null): Borrador {
  return {
    codigo: item?.codigo ?? '',
    nombre: item?.nombre ?? '',
    categoria: item?.categoria ?? '',
    descripcion: item?.descripcion ?? '',
    medidas: item?.medidas ?? '',
    etiquetas: item?.etiquetas.join(', ') ?? '',
    costo_reposicion: item?.costo_reposicion === null || item === null ? '' : String(item.costo_reposicion),
    activo: item?.activo ?? true,
    precios: Object.fromEntries((item?.precios ?? []).map((p) => [p.lista_id, String(p.precio)])),
  }
}

function aNumero(texto: string): number | null {
  const limpio = texto.replace(/[^\d.,-]/g, '').replace(/,/g, '')
  if (!limpio) return null
  const numero = Number(limpio)
  return Number.isFinite(numero) ? numero : null
}

function aEntrada(borrador: Borrador): CatalogoItemEntrada {
  const precios: Record<string, number> = {}
  for (const [listaId, texto] of Object.entries(borrador.precios)) {
    const numero = aNumero(texto)
    if (numero !== null) precios[listaId] = numero
  }
  return {
    codigo: borrador.codigo.trim().toUpperCase(),
    nombre: borrador.nombre.trim(),
    categoria: borrador.categoria.trim(),
    descripcion: borrador.descripcion.trim(),
    medidas: borrador.medidas.trim(),
    etiquetas: borrador.etiquetas
      .split(',')
      .map((e) => e.trim().toLowerCase())
      .filter(Boolean),
    costo_reposicion: aNumero(borrador.costo_reposicion),
    activo: borrador.activo,
    precios,
  }
}

export function FormularioItem({ item, listas, alCerrar, alCrear }: Props) {
  const [borrador, setBorrador] = useState<Borrador>(() => borradorDesde(item))
  const crear = useCrearItemCatalogo()
  const actualizar = useActualizarItemCatalogo()
  const guardando = crear.isPending || actualizar.isPending
  const error = crear.error ?? actualizar.error

  const cambiar = <K extends keyof Borrador>(campo: K, valor: Borrador[K]) => setBorrador((b) => ({ ...b, [campo]: valor }))

  const enviar = (evento: FormEvent) => {
    evento.preventDefault()
    const entrada = aEntrada(borrador)
    if (item) {
      actualizar.mutate({ id: item.id, cambios: entrada })
    } else {
      crear.mutate(entrada, { onSuccess: alCrear })
    }
  }

  return (
    <Modal
      abierto
      titulo={item ? `Editar ${item.codigo}` : 'Nuevo ítem del catálogo'}
      subtitulo={item ? item.nombre : 'Guarda el ítem y después sube su foto oficial.'}
      alCerrar={alCerrar}
    >
      <form onSubmit={enviar} className="flex flex-col gap-5">
        <div className="grid gap-4 sm:grid-cols-[160px_1fr_1fr]">
          <Campo etiqueta="Código" ayuda="Debe coincidir con el del sistema de la empresa.">
            <input required value={borrador.codigo} onChange={(e) => cambiar('codigo', e.target.value)} placeholder="SIL-001" />
          </Campo>
          <Campo etiqueta="Nombre">
            <input required value={borrador.nombre} onChange={(e) => cambiar('nombre', e.target.value)} placeholder="Silla Tiffany blanca" />
          </Campo>
          <Campo etiqueta="Categoría">
            <input value={borrador.categoria} onChange={(e) => cambiar('categoria', e.target.value)} placeholder="Sillas" list="categorias-catalogo" />
          </Campo>
        </div>

        <Campo etiqueta="Descripción">
          <textarea rows={3} value={borrador.descripcion} onChange={(e) => cambiar('descripcion', e.target.value)} placeholder="Material, acabado, uso recomendado…" />
        </Campo>

        <div className="grid gap-4 sm:grid-cols-2">
          <Campo etiqueta="Medidas" ayuda="Texto libre, p. ej. 45 x 50 x 95 cm">
            <input value={borrador.medidas} onChange={(e) => cambiar('medidas', e.target.value)} />
          </Campo>
          <Campo etiqueta="Etiquetas" ayuda="Separadas por coma">
            <input value={borrador.etiquetas} onChange={(e) => cambiar('etiquetas', e.target.value)} placeholder="boda, exterior, madera" />
          </Campo>
        </div>

        <fieldset className="rounded-tarjeta border border-borde p-4">
          <legend className="px-1 text-sm font-medium">Precios</legend>
          {listas.length === 0 ? (
            <p className="text-sm text-texto-secundario">No hay listas de precios activas. Créalas desde "Listas de precios".</p>
          ) : (
            <div className="grid gap-4 sm:grid-cols-3">
              {listas.map((lista) => (
                <Campo key={lista.id} etiqueta={lista.nombre}>
                  <input
                    inputMode="decimal"
                    value={borrador.precios[lista.id] ?? ''}
                    onChange={(e) => cambiar('precios', { ...borrador.precios, [lista.id]: e.target.value })}
                    placeholder="0.00"
                  />
                </Campo>
              ))}
              <Campo etiqueta="Costo de reposición" ayuda="Lo que cuesta reponer la pieza">
                <input inputMode="decimal" value={borrador.costo_reposicion} onChange={(e) => cambiar('costo_reposicion', e.target.value)} placeholder="0.00" />
              </Campo>
            </div>
          )}
        </fieldset>

        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={borrador.activo} onChange={(e) => cambiar('activo', e.target.checked)} className="h-4 w-4" />
          Ítem activo (aparece en las métricas y se puede cotizar)
        </label>

        {error && <Aviso tono="error">{mensajeDeError(error)}</Aviso>}
        {actualizar.isSuccess && !actualizar.isPending && <Aviso tono="info">Cambios guardados.</Aviso>}

        <div className="flex flex-wrap justify-end gap-2">
          <Boton variante="secundario" onClick={alCerrar}>
            {item ? 'Cerrar' : 'Cancelar'}
          </Boton>
          <Boton type="submit" cargando={guardando}>
            {item ? 'Guardar cambios' : 'Crear ítem'}
          </Boton>
        </div>
      </form>

      {item && <SeccionImagenes item={item} />}
    </Modal>
  )
}

// ---------------------------------------------------------------------------
// Imágenes del ítem: subir oficial/variante y generar con IA
// ---------------------------------------------------------------------------

function SeccionImagenes({ item }: { item: CatalogoItem }) {
  const detalle = useItemCatalogo(item.id)
  const imagenes = useImagenesDeItem(item.id)
  const subir = useSubirImagen()
  const entrada = useRef<HTMLInputElement>(null)
  const [tipoSubida, setTipoSubida] = useState<'oficial' | 'variante'>('oficial')
  const [mostrarGenerar, setMostrarGenerar] = useState(false)

  const oficial = useMemo(() => (imagenes.data ?? []).find((i) => i.tipo === 'oficial') ?? null, [imagenes.data])
  const totalImagenes = imagenes.data?.length ?? detalle.data?.total_imagenes ?? item.total_imagenes

  const elegirArchivo = (tipo: 'oficial' | 'variante') => {
    setTipoSubida(tipo)
    entrada.current?.click()
  }

  return (
    <section className="mt-6 border-t border-borde pt-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-lg">Imágenes</h3>
          <p className="text-sm text-texto-secundario">
            {totalImagenes === 0 ? 'Este ítem todavía no tiene fotos.' : `${totalImagenes} en la biblioteca.`}{' '}
            {oficial ? 'La oficial se sugiere automáticamente al cotizar.' : 'Sube la foto oficial para que se asigne sola al cotizar.'}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {!oficial && (
            <Boton icono={<Upload className="h-4 w-4" />} cargando={subir.isPending && tipoSubida === 'oficial'} onClick={() => elegirArchivo('oficial')}>
              Subir foto oficial
            </Boton>
          )}
          <Boton
            variante="secundario"
            icono={<Upload className="h-4 w-4" />}
            cargando={subir.isPending && tipoSubida === 'variante'}
            onClick={() => elegirArchivo('variante')}
          >
            Subir variante
          </Boton>
          <Boton variante={mostrarGenerar ? 'primario' : 'secundario'} icono={<Sparkles className="h-4 w-4" />} onClick={() => setMostrarGenerar((v) => !v)}>
            Generar con IA
          </Boton>
        </div>
      </div>
      <input
        ref={entrada}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        className="hidden"
        onChange={(evento) => {
          const archivo = evento.target.files?.[0]
          evento.target.value = ''
          if (archivo) subir.mutate({ archivo, itemId: item.id, tipo: tipoSubida })
        }}
      />
      {subir.isError && (
        <Aviso tono="error" className="mt-3">
          {mensajeDeError(subir.error)}
        </Aviso>
      )}

      {mostrarGenerar && (
        <div className="mt-4 rounded-tarjeta border border-borde bg-fondo/40 p-4">
          <PanelGenerar
            imagenBase={oficial ?? (imagenes.data ?? [])[0] ?? null}
            itemId={item.id}
            etiquetaBase={oficial ? 'Base: foto oficial' : 'Base: primera imagen de la biblioteca'}
          />
        </div>
      )}

      <div className="mt-4 grid grid-cols-3 gap-3 sm:grid-cols-4 md:grid-cols-6">
        {(imagenes.data ?? []).map((imagen) => (
          <div key={imagen.id} className="flex flex-col gap-1.5 rounded-tarjeta border border-borde p-2">
            <Miniatura url={imagen.url} tamano="lg" conceptual={imagen.tipo === 'generada'} className="h-auto w-full aspect-square" />
            <div className="flex items-center justify-between gap-1">
              <PildoraTipoImagen tipo={imagen.tipo} />
              <span className="text-[11px] text-texto-secundario">{imagen.usos} usos</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
