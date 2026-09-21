import { Monitor, Moon, Sun } from 'lucide-react'

import { useTema, type PreferenciaTema } from '@/lib/tema'

const ETIQUETAS: Record<PreferenciaTema, string> = {
  sistema: 'Automático',
  claro: 'Claro',
  oscuro: 'Oscuro',
}

const ICONOS = { sistema: Monitor, claro: Sun, oscuro: Moon }

/** Botón de la barra superior: alterna Automático → Claro → Oscuro. */
export function BotonTema({ className = '' }: { className?: string }) {
  const { preferencia, ciclar } = useTema()
  const Icono = ICONOS[preferencia]
  const siguiente = ETIQUETAS[preferencia === 'sistema' ? 'claro' : preferencia === 'claro' ? 'oscuro' : 'sistema']

  return (
    <button
      type="button"
      onClick={ciclar}
      title={`Tema: ${ETIQUETAS[preferencia]}. Clic para cambiar a ${siguiente}.`}
      aria-label={`Tema ${ETIQUETAS[preferencia].toLowerCase()}. Cambiar a ${siguiente.toLowerCase()}.`}
      className={`flex min-h-boton items-center gap-2 rounded-boton px-3 text-sm text-texto-secundario hover:bg-fondo hover:text-texto focus:outline-none focus-visible:ring-2 focus-visible:ring-acento/40 ${className}`}
    >
      <Icono className="h-4 w-4" aria-hidden />
      <span className="hidden xl:inline">{ETIQUETAS[preferencia]}</span>
    </button>
  )
}
