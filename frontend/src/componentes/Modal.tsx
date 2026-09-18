import { X } from 'lucide-react'
import { useEffect, type ReactNode } from 'react'

interface Props {
  abierto: boolean
  titulo: string
  subtitulo?: string
  alCerrar: () => void
  children: ReactNode
}

export function Modal({ abierto, titulo, subtitulo, alCerrar, children }: Props) {
  useEffect(() => {
    if (!abierto) return
    const alTeclear = (evento: KeyboardEvent) => {
      if (evento.key === 'Escape') alCerrar()
    }
    document.addEventListener('keydown', alTeclear)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', alTeclear)
      document.body.style.overflow = ''
    }
  }, [abierto, alCerrar])

  if (!abierto) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-texto/40 p-0 sm:items-center sm:p-6"
      onMouseDown={(evento) => {
        if (evento.target === evento.currentTarget) alCerrar()
      }}
      role="dialog"
      aria-modal="true"
      aria-label={titulo}
    >
      <div className="flex max-h-[92vh] w-full max-w-4xl flex-col overflow-hidden rounded-t-tarjeta border border-borde bg-superficie sm:rounded-tarjeta">
        <header className="flex items-start justify-between gap-4 border-b border-borde px-5 py-4">
          <div>
            <h2 className="text-xl">{titulo}</h2>
            {subtitulo && <p className="mt-0.5 text-sm text-texto-secundario">{subtitulo}</p>}
          </div>
          <button
            type="button"
            onClick={alCerrar}
            className="flex h-11 w-11 items-center justify-center rounded-boton text-texto-secundario hover:bg-borde/40 hover:text-texto"
            aria-label="Cerrar"
          >
            <X className="h-5 w-5" />
          </button>
        </header>
        <div className="overflow-y-auto px-5 py-4">{children}</div>
      </div>
    </div>
  )
}
