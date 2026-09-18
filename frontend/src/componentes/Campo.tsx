import type { ReactNode } from 'react'

export function Campo({ etiqueta, ayuda, children, className = '' }: { etiqueta: string; ayuda?: string; children: ReactNode; className?: string }) {
  return (
    <label className={`flex flex-col gap-1.5 text-sm font-medium ${className}`}>
      {etiqueta}
      {children}
      {ayuda && <span className="text-xs font-normal text-texto-secundario">{ayuda}</span>}
    </label>
  )
}

export function Chip({ activo, onClick, children }: { activo: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-pildora border px-3 py-1 text-xs font-medium ${
        activo ? 'border-texto bg-texto text-superficie' : 'border-borde text-texto-secundario hover:text-texto'
      }`}
    >
      {children}
    </button>
  )
}
