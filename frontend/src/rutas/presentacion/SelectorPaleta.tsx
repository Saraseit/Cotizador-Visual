import { Save, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { useEliminarPaleta, useGuardarPaleta, usePaletas } from '@/api/consultas'
import type { Paleta } from '@/api/tipos'
import { Aviso, mensajeDeError } from '@/componentes/Aviso'
import { Boton } from '@/componentes/Boton'
import { Campo } from '@/componentes/Campo'

const CAMPOS = [
  ['fondo', 'Fondo'],
  ['texto', 'Texto'],
  ['acento', 'Acento'],
] as const

const misma = (a: Paleta, b: Paleta) => a.fondo === b.fondo && a.texto === b.texto && a.acento === b.acento

/** Paletas de la app y del equipo, más los tres colores editables a mano. */
export function SelectorPaleta({ paleta, alCambiar }: { paleta: Paleta; alCambiar: (paleta: Paleta) => void }) {
  const consulta = usePaletas()
  const guardar = useGuardarPaleta()
  const eliminar = useEliminarPaleta()
  const [nombre, setNombre] = useState('')

  const guardadas = (consulta.data ?? []).filter((p) => !p.predefinida)
  const actual = (consulta.data ?? []).find((p) => misma(p.paleta, paleta))
  const error = guardar.error ?? eliminar.error

  return (
    <div>
      <p className="text-sm font-medium">Paleta</p>
      {error && (
        <Aviso tono="error" className="mt-2">
          {mensajeDeError(error)}
        </Aviso>
      )}

      <div className="mt-2 flex flex-wrap gap-2">
        {(consulta.data ?? []).map((guardada) => {
          const elegida = misma(guardada.paleta, paleta)
          return (
            <button
              key={`${guardada.id ?? 'app'}-${guardada.nombre}`}
              type="button"
              onClick={() => alCambiar({ ...guardada.paleta })}
              className={`flex items-center gap-2 rounded-pildora border px-3 py-1.5 text-xs font-medium ${
                elegida ? 'border-texto' : 'border-borde text-texto-secundario hover:text-texto'
              }`}
            >
              <span className="flex">
                {[guardada.paleta.fondo, guardada.paleta.texto, guardada.paleta.acento].map((color) => (
                  <span key={color} className="h-4 w-4 rounded-full border border-borde" style={{ backgroundColor: color }} />
                ))}
              </span>
              {guardada.nombre}
            </button>
          )
        })}
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        {CAMPOS.map(([campo, etiqueta]) => (
          <Campo key={campo} etiqueta={etiqueta}>
            <input
              type="color"
              className="h-10 w-full cursor-pointer p-1"
              value={paleta[campo]}
              onChange={(evento) => alCambiar({ ...paleta, [campo]: evento.target.value.toUpperCase() })}
            />
          </Campo>
        ))}
      </div>

      <div className="mt-3 flex flex-wrap items-end gap-2">
        <label className="flex flex-col gap-1.5 text-sm font-medium">
          Guardar esta paleta
          <input
            value={nombre}
            maxLength={40}
            placeholder="Nombre para el equipo"
            onChange={(evento) => setNombre(evento.target.value)}
            className="w-56"
          />
        </label>
        <Boton
          variante="secundario"
          icono={<Save className="h-4 w-4" />}
          cargando={guardar.isPending}
          disabled={!nombre.trim() || guardar.isPending}
          onClick={() => guardar.mutate({ entrada: { nombre: nombre.trim(), paleta } }, { onSuccess: () => setNombre('') })}
        >
          Guardar paleta
        </Boton>
        {actual?.id && (
          <Boton
            variante="fantasma"
            icono={<Trash2 className="h-4 w-4" />}
            disabled={eliminar.isPending}
            onClick={() => eliminar.mutate(actual.id as string)}
          >
            Borrar “{actual.nombre}”
          </Boton>
        )}
      </div>
      {guardadas.length === 0 && (
        <p className="mt-2 text-xs text-texto-secundario">
          Las que guardes aquí quedan disponibles para todo el equipo, junto a las que ya trae la app.
        </p>
      )}
    </div>
  )
}
