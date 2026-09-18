import { AlertTriangle, Info } from 'lucide-react'
import type { ReactNode } from 'react'

type Tono = 'error' | 'info' | 'ambar'

const estilos: Record<Tono, string> = {
  error: 'border-conceptual-texto/30 bg-conceptual-fondo text-conceptual-texto',
  info: 'border-borde bg-fondo text-texto-secundario',
  ambar: 'border-pendiente-borde bg-pendiente-fondo text-pendiente-texto',
}

export function Aviso({ tono = 'info', children, className = '' }: { tono?: Tono; children: ReactNode; className?: string }) {
  const Icono = tono === 'info' ? Info : AlertTriangle
  return (
    <div className={`flex items-start gap-2 rounded-boton border px-3 py-2.5 text-sm ${estilos[tono]} ${className}`} role={tono === 'error' ? 'alert' : undefined}>
      <Icono className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <div>{children}</div>
    </div>
  )
}

export function mensajeDeError(error: unknown): string {
  if (error instanceof Error) return error.message
  return 'Ocurrió un error inesperado.'
}
