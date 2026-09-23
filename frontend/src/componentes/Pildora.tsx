import type { EstadoCotizacion, EstadoItem, TipoImagen } from '@/api/tipos'

type Tono = 'pendiente' | 'resuelto' | 'conceptual' | 'neutro'

const tonos: Record<Tono, string> = {
  pendiente: 'bg-pendiente-fondo text-pendiente-texto border-pendiente-borde',
  resuelto: 'bg-resuelto-fondo text-resuelto-texto border-transparent',
  conceptual: 'bg-conceptual-fondo text-conceptual-texto border-transparent',
  neutro: 'bg-fondo text-texto-secundario border-borde',
}

export function Pildora({ tono = 'neutro', children, className = '' }: { tono?: Tono; children: React.ReactNode; className?: string }) {
  return (
    <span
      className={`inline-flex items-center whitespace-nowrap rounded-pildora border px-2.5 py-0.5 text-xs font-medium ${tonos[tono]} ${className}`}
    >
      {children}
    </span>
  )
}

export const etiquetasEstadoItem: Record<EstadoItem, { texto: string; tono: Tono }> = {
  falta_imagen: { texto: 'Falta imagen', tono: 'pendiente' },
  sugerida: { texto: 'Sugerida automáticamente', tono: 'resuelto' },
  variante: { texto: 'Variante', tono: 'resuelto' },
  render_conceptual: { texto: 'Render conceptual', tono: 'conceptual' },
}

export function PildoraEstadoItem({ estado }: { estado: EstadoItem }) {
  const { texto, tono } = etiquetasEstadoItem[estado]
  return <Pildora tono={tono}>{texto}</Pildora>
}

export function PildoraEstadoCotizacion({ estado }: { estado: EstadoCotizacion }) {
  return estado === 'generada' ? <Pildora tono="resuelto">Generada</Pildora> : <Pildora tono="pendiente">En revisión</Pildora>
}

export const etiquetasTipoImagen: Record<TipoImagen, { texto: string; tono: Tono }> = {
  oficial: { texto: 'Oficial', tono: 'resuelto' },
  variante: { texto: 'Variante', tono: 'neutro' },
  generada: { texto: 'Render conceptual', tono: 'conceptual' },
  ambientacion: { texto: 'Ambientación', tono: 'neutro' },
  montaje: { texto: 'Montaje con IA', tono: 'conceptual' },
  inspiracion: { texto: 'Inspiración', tono: 'neutro' },
}

export function PildoraTipoImagen({ tipo }: { tipo: TipoImagen }) {
  const { texto, tono } = etiquetasTipoImagen[tipo]
  return <Pildora tono={tono}>{texto}</Pildora>
}
