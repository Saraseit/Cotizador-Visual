import { ImageOff } from 'lucide-react'

interface Props {
  url: string | null | undefined
  alt?: string
  tamano?: 'sm' | 'md' | 'lg'
  conceptual?: boolean
  className?: string
}

const tamanos = { sm: 'h-14 w-14', md: 'h-24 w-24', lg: 'h-40 w-40' }

export function Miniatura({ url, alt = '', tamano = 'sm', conceptual = false, className = '' }: Props) {
  return (
    <div
      className={`relative shrink-0 overflow-hidden rounded-boton border border-borde bg-superficie ${tamanos[tamano]} ${className}`}
    >
      {url ? (
        <img src={url} alt={alt} className="h-full w-full object-contain" loading="lazy" />
      ) : (
        <div className="flex h-full w-full flex-col items-center justify-center gap-1 bg-borde/40 text-texto-secundario">
          <ImageOff className="h-4 w-4" aria-hidden />
          <span className="text-[10px] font-medium">Sin imagen</span>
        </div>
      )}
      {conceptual && url && (
        <span className="absolute left-1 top-1 rounded-sm bg-conceptual-fondo px-1 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-conceptual-texto">
          Render conceptual
        </span>
      )}
    </div>
  )
}
