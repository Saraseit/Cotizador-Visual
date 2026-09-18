import { Sparkles } from 'lucide-react'
import { useState, type ReactNode } from 'react'

import { ErrorApi } from '@/api/cliente'
import { useGenerarImagenes } from '@/api/consultas'
import type { Imagen } from '@/api/tipos'
import { Aviso, mensajeDeError } from '@/componentes/Aviso'
import { Boton } from '@/componentes/Boton'
import { Chip } from '@/componentes/Campo'
import { Miniatura } from '@/componentes/Miniatura'

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
  /** Imagen a partir de la cual se generan las variantes. */
  imagenBase: Imagen | null
  /** Ítem del catálogo al que pertenecen; null para ítems ad hoc. */
  itemId: string | null
  /** Cotización desde la que se genera (sólo para el registro de generaciones). */
  cotizacionId?: string | null
  etiquetaBase?: string
  /** Si se pasa, cada resultado tiene un botón para elegirlo; si no, sólo se guardan en la biblioteca. */
  alElegir?: (imagenId: string) => void
  ocupado?: boolean
  /** Qué mostrar cuando no hay imagen base. */
  sinBase?: ReactNode
}

export function PanelGenerar({ imagenBase, itemId, cotizacionId = null, etiquetaBase, alElegir, ocupado = false, sinBase }: Props) {
  const generar = useGenerarImagenes()
  const [peticion, setPeticion] = useState('')

  if (!imagenBase) {
    return (
      <>
        {sinBase ?? (
          <Aviso tono="ambar">
            No hay una imagen base para generar. Sube o elige primero una foto de la pieza; a partir de ella se crean las
            variantes.
          </Aviso>
        )}
      </>
    )
  }

  const agregarAtajo = (texto: string) => {
    setPeticion((actual) => (actual.trim() ? `${actual.trim()}, ${texto.toLowerCase()}` : texto))
  }

  const lanzar = () => {
    generar.mutate({ imagen_base_id: imagenBase.id, peticion: peticion.trim(), item_id: itemId, cotizacion_id: cotizacionId })
  }

  const resultados = generar.data?.imagenes ?? []
  // 429 = tope diario alcanzado: el backend explica cuál límite y cuándo se libera.
  const topeAlcanzado = generar.error instanceof ErrorApi && generar.error.estado === 429

  return (
    <div className="grid gap-6 md:grid-cols-[200px_1fr]">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-texto-secundario">Imagen base</p>
        <Miniatura url={imagenBase.url} tamano="lg" className="mt-2 h-auto w-full aspect-square" />
        <p className="mt-2 text-xs text-texto-secundario">
          {etiquetaBase ?? `Foto ${imagenBase.tipo}`}. La forma y proporciones de la pieza se conservan.
        </p>
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
              <Chip key={atajo} activo={false} onClick={() => agregarAtajo(atajo)}>
                {atajo}
              </Chip>
            ))}
          </div>
        </div>

        <Aviso tono="info">
          El ángulo (tres cuartos), el fondo neutro y la iluminación los fija el sistema. Describe sólo el acabado, material
          o color.
        </Aviso>

        <div>
          <Boton icono={<Sparkles className="h-4 w-4" />} cargando={generar.isPending} disabled={peticion.trim().length < 3} onClick={lanzar}>
            Generar 4 opciones
          </Boton>
          {generar.isPending && <p className="mt-2 text-xs text-texto-secundario">Esto tarda entre 30 y 90 segundos.</p>}
        </div>

        {generar.isError && <Aviso tono={topeAlcanzado ? 'ambar' : 'error'}>{mensajeDeError(generar.error)}</Aviso>}

        {resultados.length > 0 && (
          <div className="flex flex-col gap-3">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {resultados.map((imagen, indice) =>
                alElegir ? (
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
                ) : (
                  <div key={imagen.id} className="flex flex-col gap-1.5 rounded-tarjeta border border-borde p-2">
                    <Miniatura url={imagen.url} tamano="lg" conceptual className="h-auto w-full aspect-square" />
                    <span className="text-xs text-texto-secundario">Opción {indice + 1} · guardada en la biblioteca</span>
                  </div>
                ),
              )}
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
