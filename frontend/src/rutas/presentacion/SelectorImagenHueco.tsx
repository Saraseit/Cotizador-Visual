import { Check, Sparkles, Upload } from 'lucide-react'
import { useRef, useState } from 'react'

import { useAmbientacion, useAsignarImagenPresentacion, useGenerarMontaje, useSubirImagen } from '@/api/consultas'
import type { Imagen } from '@/api/tipos'
import { Aviso, mensajeDeError } from '@/componentes/Aviso'
import { Boton } from '@/componentes/Boton'
import { Campo } from '@/componentes/Campo'
import { Modal } from '@/componentes/Modal'

interface Props {
  cotizacionId: string
  hueco: string
  titulo: string
  /** Clave de la sección cuando el hueco es un montaje; null en los de ambientación. */
  claveSeccion: string | null
  imagenActual: Imagen | null
  alCerrar: () => void
}

/**
 * Elegir la imagen de un hueco: de la biblioteca de ambientación, subiendo una nueva, o
 * (sólo en los montajes) generándola con IA a partir de las fotos de las piezas de la sección.
 */
export function SelectorImagenHueco({ cotizacionId, hueco, titulo, claveSeccion, imagenActual, alCerrar }: Props) {
  const biblioteca = useAmbientacion()
  const asignar = useAsignarImagenPresentacion(cotizacionId)
  const subir = useSubirImagen()
  const generar = useGenerarMontaje(cotizacionId)
  const [indicaciones, setIndicaciones] = useState('')
  const archivo = useRef<HTMLInputElement>(null)

  const ocupado = asignar.isPending || subir.isPending || generar.isPending
  const error = asignar.error ?? subir.error ?? generar.error

  const elegir = (imagenId: string | null) => asignar.mutate({ hueco, imagenId }, { onSuccess: alCerrar })

  const alSubir = (archivos: FileList | null) => {
    const uno = archivos?.[0]
    if (!uno) return
    subir.mutate(
      { archivo: uno, tipo: 'ambientacion', etiquetas: ['ambientacion'] },
      { onSuccess: (imagen) => asignar.mutate({ hueco, imagenId: imagen.id }, { onSuccess: alCerrar }) },
    )
  }

  return (
    <Modal
      abierto
      titulo={titulo}
      subtitulo={
        claveSeccion !== null
          ? 'Sube tu propia foto del montaje, elígela de la biblioteca o genérala con IA.'
          : 'Elige una foto de ambientación de la biblioteca o sube una nueva.'
      }
      alCerrar={alCerrar}
    >
      {error && (
        <Aviso tono="error" className="mb-4">
          {mensajeDeError(error)}
        </Aviso>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <input
          ref={archivo}
          type="file"
          accept="image/png,image/jpeg,image/webp"
          className="hidden"
          onChange={(evento) => alSubir(evento.target.files)}
        />
        <Boton
          variante="secundario"
          icono={<Upload className="h-4 w-4" />}
          cargando={subir.isPending}
          disabled={ocupado}
          onClick={() => archivo.current?.click()}
        >
          Subir una foto
        </Boton>
        {imagenActual && (
          <Boton variante="fantasma" disabled={ocupado} onClick={() => elegir(null)}>
            Quitar la imagen actual
          </Boton>
        )}
      </div>

      {claveSeccion !== null && (
        <section className="mt-5 rounded-tarjeta border border-borde p-4">
          <h3 className="text-base font-semibold">Generar el montaje con IA</h3>
          <p className="mt-1 text-sm text-texto-secundario">
            Usa tus indicaciones de la presentación y las fotos de las piezas de esta sección como referencia. Tarda hasta un minuto y
            consume una generación de tu límite diario.
          </p>
          <Campo etiqueta="Algo más para esta imagen (opcional)" className="mt-3">
            <textarea
              rows={2}
              value={indicaciones}
              disabled={ocupado}
              onChange={(evento) => setIndicaciones(evento.target.value)}
              placeholder="Por ejemplo: de noche, con velas en las mesas y la pérgola al fondo."
            />
          </Campo>
          <Boton
            className="mt-3"
            icono={<Sparkles className="h-4 w-4" />}
            cargando={generar.isPending}
            disabled={ocupado}
            onClick={() => generar.mutate({ clave: claveSeccion, indicaciones }, { onSuccess: alCerrar })}
          >
            Generar montaje
          </Boton>
        </section>
      )}

      <h3 className="mt-6 text-base font-semibold">Biblioteca de ambientación</h3>
      {biblioteca.isLoading && <p className="mt-2 text-sm text-texto-secundario">Cargando imágenes…</p>}
      {biblioteca.data?.length === 0 && (
        <p className="mt-2 text-sm text-texto-secundario">
          Todavía no hay fotos de ambientación. Sube la primera: quedará disponible para todas las propuestas.
        </p>
      )}
      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
        {(biblioteca.data ?? []).map((imagen) => {
          const elegida = imagen.id === imagenActual?.id
          return (
            <button
              key={imagen.id}
              type="button"
              disabled={ocupado}
              onClick={() => elegir(imagen.id)}
              className={`relative aspect-[4/3] overflow-hidden rounded-tarjeta border-2 transition-colors ${
                elegida ? 'border-acento' : 'border-borde hover:border-texto-secundario'
              }`}
            >
              {imagen.url ? (
                <img src={imagen.url} alt="" className="h-full w-full object-cover" />
              ) : (
                <span className="flex h-full items-center justify-center text-xs text-texto-secundario">Sin vista previa</span>
              )}
              {elegida && (
                <span className="absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded-full bg-acento text-superficie">
                  <Check className="h-4 w-4" />
                </span>
              )}
            </button>
          )
        })}
      </div>
    </Modal>
  )
}
