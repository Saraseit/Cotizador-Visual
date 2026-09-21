import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'

import { Aviso } from '@/componentes/Aviso'
import { Boton } from '@/componentes/Boton'
import { BotonTema } from '@/componentes/BotonTema'
import { useSesion } from '@/lib/sesion'
import { supabase } from '@/lib/supabase'

export function Entrar() {
  const { sesion } = useSesion()
  const navegar = useNavigate()
  const ubicacion = useLocation()
  const [correo, setCorreo] = useState('')
  const [contrasena, setContrasena] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  if (sesion) {
    const destino = (ubicacion.state as { desde?: string } | null)?.desde ?? '/'
    return <Navigate to={destino} replace />
  }

  const enviar = async (evento: FormEvent) => {
    evento.preventDefault()
    setError(null)
    setEnviando(true)
    const { error: errorAuth } = await supabase.auth.signInWithPassword({ email: correo, password: contrasena })
    setEnviando(false)
    if (errorAuth) {
      setError('Correo o contraseña incorrectos.')
      return
    }
    navegar('/', { replace: true })
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <BotonTema className="absolute right-4 top-4" />
      <div className="tarjeta w-full max-w-sm p-8">
        <h1 className="text-2xl">ProVista</h1>
        <p className="mt-1 text-sm text-texto-secundario">Minimal 4.0 · herramienta interna</p>

        <form onSubmit={enviar} className="mt-8 flex flex-col gap-4">
          <label className="flex flex-col gap-1.5 text-sm font-medium">
            Correo
            <input
              type="email"
              autoComplete="email"
              required
              value={correo}
              onChange={(evento) => setCorreo(evento.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1.5 text-sm font-medium">
            Contraseña
            <input
              type="password"
              autoComplete="current-password"
              required
              value={contrasena}
              onChange={(evento) => setContrasena(evento.target.value)}
            />
          </label>
          {error && <Aviso tono="error">{error}</Aviso>}
          <Boton type="submit" cargando={enviando} className="mt-2 w-full">
            Entrar
          </Boton>
        </form>
        <p className="mt-6 text-xs text-texto-secundario">
          Las cuentas las crea el administrador en Supabase. Si no tienes acceso, pídelo al equipo.
        </p>
      </div>
    </div>
  )
}
