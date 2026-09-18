import type { ButtonHTMLAttributes, ReactNode } from 'react'

type Variante = 'primario' | 'secundario' | 'fantasma'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variante?: Variante
  icono?: ReactNode
  cargando?: boolean
}

const estilos: Record<Variante, string> = {
  primario: 'bg-acento text-superficie hover:bg-acento-oscuro disabled:bg-acento/50',
  secundario: 'border border-borde bg-superficie text-texto hover:border-texto-secundario disabled:text-texto-secundario/60',
  fantasma: 'text-texto-secundario hover:bg-borde/40 hover:text-texto',
}

export function Boton({ variante = 'primario', icono, cargando, className = '', children, disabled, ...resto }: Props) {
  return (
    <button
      type="button"
      className={`inline-flex min-h-boton items-center justify-center gap-2 rounded-boton px-4 text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-acento/40 disabled:cursor-not-allowed ${estilos[variante]} ${className}`}
      disabled={disabled || cargando}
      {...resto}
    >
      {cargando ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" /> : icono}
      {children}
    </button>
  )
}
