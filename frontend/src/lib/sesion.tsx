import type { Session } from '@supabase/supabase-js'
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'

import { supabase } from './supabase'

interface EstadoSesion {
  sesion: Session | null
  cargando: boolean
  salir: () => Promise<void>
}

const ContextoSesion = createContext<EstadoSesion | null>(null)

export function ProveedorSesion({ children }: { children: ReactNode }) {
  const [sesion, setSesion] = useState<Session | null>(null)
  const [cargando, setCargando] = useState(true)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSesion(data.session)
      setCargando(false)
    })
    const { data: escucha } = supabase.auth.onAuthStateChange((_evento, nueva) => setSesion(nueva))
    return () => escucha.subscription.unsubscribe()
  }, [])

  const salir = async () => {
    await supabase.auth.signOut()
  }

  return <ContextoSesion.Provider value={{ sesion, cargando, salir }}>{children}</ContextoSesion.Provider>
}

export function useSesion(): EstadoSesion {
  const contexto = useContext(ContextoSesion)
  if (!contexto) throw new Error('useSesion debe usarse dentro de ProveedorSesion')
  return contexto
}

export function RutaProtegida({ children }: { children: ReactNode }) {
  const { sesion, cargando } = useSesion()
  const ubicacion = useLocation()
  if (cargando) {
    return <div className="p-10 text-center text-texto-secundario">Cargando sesión…</div>
  }
  if (!sesion) {
    return <Navigate to="/entrar" replace state={{ desde: ubicacion.pathname }} />
  }
  return <>{children}</>
}
