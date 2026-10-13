import { KeyRound, ShieldCheck } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import { useCambiarContrasena, usePerfil } from '@/api/consultas'
import { Aviso, mensajeDeError } from '@/componentes/Aviso'
import { Boton } from '@/componentes/Boton'
import { Campo } from '@/componentes/Campo'
import { Pildora } from '@/componentes/Pildora'
import { useSesion } from '@/lib/sesion'

const VACIO = { actual: '', nueva: '', confirmar: '' }

function FormularioContrasena() {
  const cambiar = useCambiarContrasena()
  const [datos, setDatos] = useState(VACIO)
  const [listo, setListo] = useState(false)

  // Lo que el navegador no puede verificar solo: que la nueva coincida y que de verdad sea otra.
  const noCoincide = datos.confirmar.length > 0 && datos.nueva !== datos.confirmar
  const esLaMisma = datos.nueva.length > 0 && datos.nueva === datos.actual
  const puedeEnviar = datos.actual.length > 0 && datos.nueva.length >= 8 && !noCoincide && !esLaMisma

  const enviar = (evento: FormEvent) => {
    evento.preventDefault()
    if (!puedeEnviar) return
    cambiar.mutate(
      { contrasena_actual: datos.actual, contrasena_nueva: datos.nueva },
      {
        onSuccess: () => {
          setDatos(VACIO)
          setListo(true)
        },
      },
    )
  }

  const escribir = (campo: keyof typeof VACIO) => (evento: { target: { value: string } }) => {
    setListo(false)
    setDatos((previo) => ({ ...previo, [campo]: evento.target.value }))
  }

  return (
    <form onSubmit={enviar} className="tarjeta mt-6 flex max-w-xl flex-col gap-4 p-5">
      <div>
        <h2 className="flex items-center gap-2 text-lg">
          <KeyRound className="h-4 w-4" aria-hidden />
          Cambiar mi contraseña
        </h2>
        <p className="mt-1 text-sm text-texto-secundario">
          Tu sesión sigue abierta después del cambio. La nueva contraseña aplica la próxima vez que entres.
        </p>
      </div>

      <Campo etiqueta="Contraseña actual">
        <input type="password" required autoComplete="current-password" value={datos.actual} onChange={escribir('actual')} />
      </Campo>
      <Campo etiqueta="Contraseña nueva" ayuda="Mínimo 8 caracteres.">
        <input type="password" required minLength={8} autoComplete="new-password" value={datos.nueva} onChange={escribir('nueva')} />
      </Campo>
      <Campo etiqueta="Repetir la nueva">
        <input type="password" required autoComplete="new-password" value={datos.confirmar} onChange={escribir('confirmar')} />
      </Campo>

      {noCoincide && <Aviso tono="ambar">Las dos contraseñas nuevas no son iguales.</Aviso>}
      {esLaMisma && <Aviso tono="ambar">La contraseña nueva tiene que ser distinta de la actual.</Aviso>}
      {cambiar.isError && <Aviso tono="error">{mensajeDeError(cambiar.error)}</Aviso>}
      {listo && <Aviso tono="exito">Contraseña cambiada. Ya avisamos al administrador del cambio.</Aviso>}

      <Aviso tono="info">
        Por seguridad, cada cambio —y cada intento con la contraseña actual equivocada— queda registrado y aparece en la pantalla de
        Usuarios del administrador, con tu nombre y la fecha. Nadie ve tu contraseña.
      </Aviso>

      <div className="flex justify-end">
        <Boton type="submit" disabled={!puedeEnviar} cargando={cambiar.isPending}>
          Cambiar contraseña
        </Boton>
      </div>
    </form>
  )
}

export function Perfil() {
  const { sesion } = useSesion()
  const perfil = usePerfil()
  const correo = perfil.data?.email ?? sesion?.user.email ?? '—'

  return (
    <div>
      <header>
        <h1 className="text-3xl">Mi cuenta</h1>
        <p className="mt-1 text-texto-secundario">Tus datos de acceso. Lo demás lo administra quien lleva la plataforma.</p>
      </header>

      <div className="tarjeta mt-6 flex max-w-xl flex-col gap-3 p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="font-medium">{perfil.data?.nombre || correo}</p>
            <p className="text-sm text-texto-secundario">{correo}</p>
          </div>
          <Pildora tono={perfil.data?.rol === 'admin' ? 'resuelto' : 'neutro'}>
            {perfil.data?.rol === 'admin' ? 'Administrador' : 'Vendedor'}
          </Pildora>
        </div>
        <p className="flex items-start gap-2 text-sm text-texto-secundario">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          Para cambiar tu nombre o tu rol, pide a un administrador que lo ajuste desde Usuarios.
        </p>
      </div>

      <FormularioContrasena />
    </div>
  )
}
