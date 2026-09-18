import { KeyRound, Plus, Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import { useActualizarUsuario, useCrearUsuario, useEliminarUsuario, usePerfil, useUsuarios } from '@/api/consultas'
import type { Rol, UsuarioAdmin } from '@/api/tipos'
import { Aviso, mensajeDeError } from '@/componentes/Aviso'
import { Boton } from '@/componentes/Boton'
import { Campo } from '@/componentes/Campo'
import { Modal } from '@/componentes/Modal'
import { Pildora } from '@/componentes/Pildora'
import { fecha } from '@/lib/formato'

function FormularioNuevo({ alCerrar }: { alCerrar: () => void }) {
  const crear = useCrearUsuario()
  const [datos, setDatos] = useState({ email: '', contrasena: '', nombre: '', rol: 'vendedor' as Rol })

  const enviar = (evento: FormEvent) => {
    evento.preventDefault()
    crear.mutate(datos, { onSuccess: alCerrar })
  }

  return (
    <Modal abierto titulo="Nuevo usuario" subtitulo="Queda activo de inmediato; comparte la contraseña con la persona." alCerrar={alCerrar}>
      <form onSubmit={enviar} className="flex flex-col gap-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo etiqueta="Correo">
            <input type="email" required autoComplete="off" value={datos.email} onChange={(e) => setDatos({ ...datos, email: e.target.value })} />
          </Campo>
          <Campo etiqueta="Nombre">
            <input value={datos.nombre} onChange={(e) => setDatos({ ...datos, nombre: e.target.value })} placeholder="Como aparecerá en la app" />
          </Campo>
          <Campo etiqueta="Contraseña" ayuda="Mínimo 8 caracteres">
            <input type="text" required minLength={8} autoComplete="new-password" value={datos.contrasena} onChange={(e) => setDatos({ ...datos, contrasena: e.target.value })} />
          </Campo>
          <Campo etiqueta="Rol">
            <select value={datos.rol} onChange={(e) => setDatos({ ...datos, rol: e.target.value as Rol })}>
              <option value="vendedor">Vendedor</option>
              <option value="admin">Administrador</option>
            </select>
          </Campo>
        </div>
        {crear.isError && <Aviso tono="error">{mensajeDeError(crear.error)}</Aviso>}
        <div className="flex justify-end gap-2">
          <Boton variante="secundario" onClick={alCerrar}>
            Cancelar
          </Boton>
          <Boton type="submit" cargando={crear.isPending}>
            Crear usuario
          </Boton>
        </div>
      </form>
    </Modal>
  )
}

function CambiarContrasena({ usuario, alCerrar }: { usuario: UsuarioAdmin; alCerrar: () => void }) {
  const actualizar = useActualizarUsuario()
  const [contrasena, setContrasena] = useState('')

  const enviar = (evento: FormEvent) => {
    evento.preventDefault()
    actualizar.mutate({ id: usuario.id, cambios: { contrasena } }, { onSuccess: alCerrar })
  }

  return (
    <Modal abierto titulo="Cambiar contraseña" subtitulo={usuario.email ?? ''} alCerrar={alCerrar}>
      <form onSubmit={enviar} className="flex flex-col gap-4">
        <Campo etiqueta="Nueva contraseña" ayuda="Mínimo 8 caracteres. La persona podrá entrar con ella de inmediato.">
          <input type="text" required minLength={8} autoComplete="new-password" value={contrasena} onChange={(e) => setContrasena(e.target.value)} />
        </Campo>
        {actualizar.isError && <Aviso tono="error">{mensajeDeError(actualizar.error)}</Aviso>}
        <div className="flex justify-end gap-2">
          <Boton variante="secundario" onClick={alCerrar}>
            Cancelar
          </Boton>
          <Boton type="submit" cargando={actualizar.isPending}>
            Guardar
          </Boton>
        </div>
      </form>
    </Modal>
  )
}

function FilaUsuario({ usuario, esYo, alCambiarContrasena }: { usuario: UsuarioAdmin; esYo: boolean; alCambiarContrasena: () => void }) {
  const actualizar = useActualizarUsuario()
  const eliminar = useEliminarUsuario()
  const [nombre, setNombre] = useState(usuario.nombre)
  const error = actualizar.error ?? eliminar.error

  const confirmarEliminar = () => {
    if (window.confirm(`¿Eliminar a ${usuario.email}? Sus cotizaciones también se borran.`)) {
      eliminar.mutate(usuario.id)
    }
  }

  return (
    <tr>
      <td className="px-4 py-3 align-top">
        <p className="font-medium">{usuario.email}</p>
        {esYo && <Pildora tono="neutro" className="mt-1">Tú</Pildora>}
      </td>
      <td className="px-4 py-3 align-top">
        <input
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          onBlur={() => nombre.trim() !== usuario.nombre && actualizar.mutate({ id: usuario.id, cambios: { nombre: nombre.trim() } })}
          className="w-full min-w-[140px]"
          aria-label={`Nombre de ${usuario.email}`}
        />
      </td>
      <td className="px-4 py-3 align-top">
        <select
          value={usuario.rol}
          disabled={esYo}
          onChange={(e) => actualizar.mutate({ id: usuario.id, cambios: { rol: e.target.value as Rol } })}
          aria-label={`Rol de ${usuario.email}`}
        >
          <option value="vendedor">Vendedor</option>
          <option value="admin">Administrador</option>
        </select>
      </td>
      <td className="px-4 py-3 align-top text-texto-secundario">{usuario.creado_en ? fecha(usuario.creado_en) : '—'}</td>
      <td className="px-4 py-3 align-top text-texto-secundario">{usuario.ultimo_acceso ? fecha(usuario.ultimo_acceso) : 'Nunca'}</td>
      <td className="px-4 py-3 text-right align-top">
        <div className="flex justify-end gap-2">
          <Boton variante="secundario" icono={<KeyRound className="h-4 w-4" />} onClick={alCambiarContrasena}>
            Contraseña
          </Boton>
          <Boton variante="fantasma" icono={<Trash2 className="h-4 w-4" />} disabled={esYo} cargando={eliminar.isPending} onClick={confirmarEliminar} aria-label="Eliminar">
            Eliminar
          </Boton>
        </div>
        {error && <p className="mt-1 text-right text-xs text-conceptual-texto">{mensajeDeError(error)}</p>}
      </td>
    </tr>
  )
}

export function Usuarios() {
  const perfil = usePerfil()
  const esAdmin = perfil.data?.rol === 'admin'
  const usuarios = useUsuarios(esAdmin)
  const [ventana, setVentana] = useState<{ tipo: 'nuevo' } | { tipo: 'contrasena'; usuario: UsuarioAdmin } | null>(null)

  if (perfil.isLoading) return <p className="text-texto-secundario">Cargando…</p>
  if (!esAdmin) return <Aviso tono="ambar">Esta sección es sólo para administradores.</Aviso>

  return (
    <div>
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl">Usuarios</h1>
          <p className="mt-1 text-texto-secundario">Altas, roles y contraseñas del equipo, sin pasar por Supabase.</p>
        </div>
        <Boton icono={<Plus className="h-4 w-4" />} onClick={() => setVentana({ tipo: 'nuevo' })}>
          Nuevo usuario
        </Boton>
      </header>

      {usuarios.isError && (
        <Aviso tono="error" className="mt-4">
          {mensajeDeError(usuarios.error)}
        </Aviso>
      )}

      <div className="tarjeta mt-6 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="border-b border-borde bg-fondo/60 text-left text-xs uppercase tracking-wide text-texto-secundario">
            <tr>
              <th className="px-4 py-3 font-semibold">Correo</th>
              <th className="px-4 py-3 font-semibold">Nombre</th>
              <th className="px-4 py-3 font-semibold">Rol</th>
              <th className="px-4 py-3 font-semibold">Alta</th>
              <th className="px-4 py-3 font-semibold">Último acceso</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-borde">
            {usuarios.isLoading && (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-texto-secundario">
                  Cargando usuarios…
                </td>
              </tr>
            )}
            {usuarios.data?.map((usuario) => (
              <FilaUsuario
                key={usuario.id}
                usuario={usuario}
                esYo={usuario.id === perfil.data?.id}
                alCambiarContrasena={() => setVentana({ tipo: 'contrasena', usuario })}
              />
            ))}
          </tbody>
        </table>
      </div>

      {ventana?.tipo === 'nuevo' && <FormularioNuevo alCerrar={() => setVentana(null)} />}
      {ventana?.tipo === 'contrasena' && <CambiarContrasena usuario={ventana.usuario} alCerrar={() => setVentana(null)} />}
    </div>
  )
}
