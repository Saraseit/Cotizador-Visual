import { Check, ImagePlus, RefreshCw, Sparkles, Trash2 } from 'lucide-react'
import { useRef, useState } from 'react'

import { useActualizarPlantilla, useAnalizarPlantilla, useCrearPlantilla, useEliminarPlantilla, usePlantillas } from '@/api/consultas'
import type { Composicion, Plantilla } from '@/api/tipos'
import { Aviso, mensajeDeError } from '@/componentes/Aviso'
import { Boton } from '@/componentes/Boton'
import { Pildora } from '@/componentes/Pildora'

export const NOMBRE_COMPOSICION: Record<Composicion, string> = {
  editorial: 'Editorial',
  revista: 'Revista',
  catalogo: 'Catálogo',
}

function Muestras({ plantilla }: { plantilla: Plantilla }) {
  const { fondo, texto, acento } = plantilla.parametros.paleta
  return (
    <span className="flex">
      {[fondo, texto, acento].map((color) => (
        <span key={color} className="h-4 w-4 rounded-full border border-borde" style={{ backgroundColor: color }} />
      ))}
    </span>
  )
}

interface Props {
  plantillaId: string | null
  /** Copia los parámetros de la plantilla a esta propuesta (la plantilla no cambia después). */
  alAplicar: (plantilla: Plantilla) => void
}

/**
 * Biblioteca de plantillas: cada una nace de una inspiración que sube el vendedor y que la IA lee
 * para proponer composición, paleta y tipografía. Aplicarla copia sus parámetros a la propuesta.
 */
export function SelectorPlantilla({ plantillaId, alAplicar }: Props) {
  const consulta = usePlantillas()
  const crear = useCrearPlantilla()
  const analizar = useAnalizarPlantilla()
  const eliminar = useEliminarPlantilla()
  const renombrar = useActualizarPlantilla()
  const archivo = useRef<HTMLInputElement>(null)
  const [nombre, setNombre] = useState('')

  const ocupado = crear.isPending || analizar.isPending || eliminar.isPending
  // Si la plantilla se borró, el id queda colgando: no se anuncia como aplicada.
  const aplicada = (consulta.data ?? []).some((p) => p.id === plantillaId)
  const error = crear.error ?? analizar.error ?? eliminar.error ?? renombrar.error

  const subir = (archivos: FileList | null) => {
    const uno = archivos?.[0]
    if (!uno) return
    crear.mutate({ archivo: uno, nombre }, { onSuccess: () => setNombre('') })
  }

  return (
    <section className="tarjeta p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl">Plantilla</h2>
        {aplicada && <Pildora tono="resuelto">Aplicada</Pildora>}
      </div>
      <p className="mt-1 text-sm text-texto-secundario">
        Sube una imagen que te guste como referencia. La IA la lee y propone composición, paleta, tipografía y cuántas piezas van por
        página. Después ajustas lo que quieras abajo.
      </p>

      {error && (
        <Aviso tono="error" className="mt-4">
          {mensajeDeError(error)}
        </Aviso>
      )}

      <div className="mt-4 flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1.5 text-sm font-medium">
          Nombre (opcional)
          <input
            value={nombre}
            maxLength={60}
            onChange={(evento) => setNombre(evento.target.value)}
            placeholder="Lo pone la IA si lo dejas vacío"
            className="w-64"
          />
        </label>
        <input
          ref={archivo}
          type="file"
          accept="image/png,image/jpeg,image/webp"
          className="hidden"
          onChange={(evento) => subir(evento.target.files)}
        />
        <Boton
          icono={<ImagePlus className="h-4 w-4" />}
          cargando={crear.isPending}
          disabled={ocupado}
          onClick={() => archivo.current?.click()}
        >
          Subir inspiración
        </Boton>
      </div>
      {crear.isPending && <p className="mt-2 text-xs text-texto-secundario">Leyendo la inspiración, unos segundos…</p>}

      {consulta.isLoading && <p className="mt-4 text-sm text-texto-secundario">Cargando plantillas…</p>}
      {consulta.data?.length === 0 && (
        <p className="mt-4 text-sm text-texto-secundario">
          Todavía no hay plantillas. La propuesta sale con el diseño editorial de la presentación de ejemplo.
        </p>
      )}

      <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {(consulta.data ?? []).map((plantilla) => {
          const aplicada = plantilla.id === plantillaId
          const portada = plantilla.inspiraciones[0]
          return (
            <div key={plantilla.id} className={`overflow-hidden rounded-tarjeta border ${aplicada ? 'border-acento' : 'border-borde'}`}>
              <button
                type="button"
                onClick={() => alAplicar(plantilla)}
                disabled={ocupado}
                className="relative block aspect-[4/3] w-full bg-fondo transition-opacity hover:opacity-90"
                aria-label={`Usar la plantilla ${plantilla.nombre}`}
              >
                {portada?.url ? (
                  <img src={portada.url} alt="" className="h-full w-full object-cover" />
                ) : (
                  <span className="flex h-full items-center justify-center text-sm text-texto-secundario">Sin inspiración</span>
                )}
                {aplicada && (
                  <span className="absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded-full bg-acento text-superficie">
                    <Check className="h-4 w-4" />
                  </span>
                )}
              </button>
              <div className="space-y-2 p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="truncate text-sm font-medium">{plantilla.nombre}</p>
                  <Muestras plantilla={plantilla} />
                </div>
                <p className="text-xs text-texto-secundario">
                  {NOMBRE_COMPOSICION[plantilla.parametros.composicion]} · {plantilla.parametros.piezas_por_pagina} por página
                  {plantilla.inspiraciones.length > 1 && ` · ${plantilla.inspiraciones.length} inspiraciones`}
                </p>
                {plantilla.descripcion && <p className="text-xs text-texto-secundario">{plantilla.descripcion}</p>}
                <div className="flex flex-wrap items-center gap-2 pt-1">
                  <Boton variante="secundario" disabled={ocupado} onClick={() => alAplicar(plantilla)}>
                    {aplicada ? 'Volver a aplicar' : 'Usar'}
                  </Boton>
                  <Boton
                    variante="fantasma"
                    icono={<RefreshCw className="h-4 w-4" />}
                    cargando={analizar.isPending && analizar.variables === plantilla.id}
                    disabled={ocupado || plantilla.inspiraciones.length === 0}
                    onClick={() => analizar.mutate(plantilla.id)}
                    title="Volver a leer la inspiración con IA"
                  >
                    Releer
                  </Boton>
                  <Boton
                    variante="fantasma"
                    icono={<Trash2 className="h-4 w-4" />}
                    disabled={ocupado}
                    onClick={() => eliminar.mutate(plantilla.id)}
                    title="Borrar la plantilla"
                  >
                    Borrar
                  </Boton>
                </div>
              </div>
            </div>
          )
        })}
      </div>

      <p className="mt-4 flex items-start gap-2 text-xs text-texto-secundario">
        <Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        Las inspiraciones de la plantilla aplicada también se mandan como referencia de estilo cuando generas los montajes con IA. Si la IA
        no está disponible, al menos se toma la paleta de la imagen.
      </p>
    </section>
  )
}
