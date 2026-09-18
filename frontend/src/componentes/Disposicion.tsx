import { Check, Library, LogOut } from 'lucide-react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'

import { useSesion } from '@/lib/sesion'

const PASOS = ['Subir', 'Revisar', 'Generar'] as const

function pasoActual(ruta: string): number {
  if (/^\/cotizaciones\/[^/]+\/generar/.test(ruta)) return 3
  if (/^\/cotizaciones\/[^/]+/.test(ruta)) return 2
  if (ruta === '/') return 1
  return 0
}

function IndicadorProgreso({ actual }: { actual: number }) {
  return (
    <ol className="hidden items-center gap-1 md:flex" aria-label="Progreso">
      {PASOS.map((nombre, indice) => {
        const numero = indice + 1
        const completado = numero < actual
        const activo = numero === actual
        return (
          <li key={nombre} className="flex items-center gap-1">
            <span
              className={`flex items-center gap-2 rounded-pildora px-3 py-1 text-sm ${
                activo ? 'bg-texto text-superficie' : completado ? 'text-resuelto-texto' : 'text-texto-secundario'
              }`}
            >
              <span
                className={`flex h-5 w-5 items-center justify-center rounded-full border text-[11px] font-semibold ${
                  activo
                    ? 'border-superficie/40'
                    : completado
                      ? 'border-resuelto-texto bg-resuelto-fondo'
                      : 'border-borde'
                }`}
              >
                {completado ? <Check className="h-3 w-3" /> : numero}
              </span>
              {nombre}
            </span>
            {indice < PASOS.length - 1 && <span className="h-px w-6 bg-borde" aria-hidden />}
          </li>
        )
      })}
    </ol>
  )
}

export function Disposicion() {
  const { sesion, salir } = useSesion()
  const ubicacion = useLocation()

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b border-borde bg-superficie/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-6 px-4 sm:px-6">
          <Link to="/" className="font-titulo text-lg font-semibold tracking-tight">
            Cotizador visual
          </Link>
          <IndicadorProgreso actual={pasoActual(ubicacion.pathname)} />
          <nav className="flex items-center gap-1">
            <NavLink
              to="/biblioteca"
              className={({ isActive }) =>
                `flex min-h-boton items-center gap-2 rounded-boton px-3 text-sm ${
                  isActive ? 'bg-fondo text-texto' : 'text-texto-secundario hover:bg-fondo hover:text-texto'
                }`
              }
            >
              <Library className="h-4 w-4" />
              <span className="hidden sm:inline">Biblioteca</span>
            </NavLink>
            <span className="hidden max-w-[180px] truncate px-2 text-sm text-texto-secundario lg:inline" title={sesion?.user.email ?? ''}>
              {sesion?.user.email}
            </span>
            <button
              type="button"
              onClick={() => void salir()}
              className="flex min-h-boton items-center gap-2 rounded-boton px-3 text-sm text-texto-secundario hover:bg-fondo hover:text-texto"
            >
              <LogOut className="h-4 w-4" />
              <span className="hidden sm:inline">Salir</span>
            </button>
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6">
        <Outlet />
      </main>
    </div>
  )
}
