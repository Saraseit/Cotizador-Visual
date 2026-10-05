import { ImageOff, Plus, RotateCcw, Save, Trash2, Upload } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { useAjustesPropuesta, useGuardarAjustes, usePerfil, useQuitarImagenAjustes, useSubirImagenAjustes } from '@/api/consultas'
import type { AjustesPropuesta, AjustesPropuestaEntrada, CampoPropuesta, HuecoMarca, TipoCampo } from '@/api/tipos'
import { Aviso, mensajeDeError } from '@/componentes/Aviso'
import { Boton } from '@/componentes/Boton'
import { Campo } from '@/componentes/Campo'

const TIPOS: [TipoCampo, string][] = [
  ['texto', 'Texto libre'],
  ['fecha', 'Fecha'],
  ['hora', 'Hora'],
]

const entradaDe = (ajustes: AjustesPropuesta): AjustesPropuestaEntrada => ({
  titulo: ajustes.titulo,
  subtitulo: ajustes.subtitulo,
  notas_titulo: ajustes.notas_titulo,
  notas: ajustes.notas,
  campos: ajustes.campos.map((c) => ({ ...c })),
})

const idNuevo = () => `c${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`

/** Tipo del <input> según el campo: el navegador muestra el selector de fecha u hora. */
export const tipoDeInput = (tipo: TipoCampo) => (tipo === 'fecha' ? 'date' : tipo === 'hora' ? 'time' : 'text')

function ImagenMarca({
  hueco,
  titulo,
  ayuda,
  url,
  vacia,
  puedeQuitar,
  etiquetaQuitar,
  editable,
}: {
  hueco: HuecoMarca
  titulo: string
  ayuda: string
  url: string | null
  vacia: string
  puedeQuitar: boolean
  etiquetaQuitar: string
  editable: boolean
}) {
  const entrada = useRef<HTMLInputElement>(null)
  const subir = useSubirImagenAjustes()
  const quitar = useQuitarImagenAjustes()
  const error = subir.error ?? quitar.error

  return (
    <div className="flex flex-col gap-3">
      <div>
        <p className="text-sm font-medium">{titulo}</p>
        <p className="text-xs text-texto-secundario">{ayuda}</p>
      </div>
      <div className="flex h-28 items-center justify-center rounded-tarjeta border border-borde bg-white p-4">
        {url ? (
          <img src={url} alt={titulo} className="max-h-full max-w-full object-contain" />
        ) : (
          <span className="flex items-center gap-2 text-center text-sm text-texto-secundario">
            <ImageOff className="h-4 w-4 shrink-0" aria-hidden /> {vacia}
          </span>
        )}
      </div>
      {editable && (
        <div className="flex flex-wrap gap-2">
          <Boton variante="secundario" icono={<Upload className="h-4 w-4" />} cargando={subir.isPending} onClick={() => entrada.current?.click()}>
            Subir imagen
          </Boton>
          {puedeQuitar && (
            <Boton variante="fantasma" icono={<RotateCcw className="h-4 w-4" />} cargando={quitar.isPending} onClick={() => quitar.mutate(hueco)}>
              {etiquetaQuitar}
            </Boton>
          )}
          <input
            ref={entrada}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            className="hidden"
            onChange={(evento) => {
              const archivo = evento.target.files?.[0]
              evento.target.value = ''
              if (archivo) subir.mutate({ hueco, archivo })
            }}
          />
        </div>
      )}
      {error && <Aviso tono="error">{mensajeDeError(error)}</Aviso>}
    </div>
  )
}

function FilaCampo({
  campo,
  editable,
  alCambiar,
  alQuitar,
}: {
  campo: CampoPropuesta
  editable: boolean
  alCambiar: (campo: CampoPropuesta) => void
  alQuitar: () => void
}) {
  return (
    <li className="grid gap-3 py-3 sm:grid-cols-[1fr_9rem_1fr_auto] sm:items-end">
      <Campo etiqueta="Etiqueta">
        <input
          value={campo.etiqueta}
          maxLength={40}
          disabled={!editable}
          placeholder="Ej. Fecha del evento"
          onChange={(e) => alCambiar({ ...campo, etiqueta: e.target.value })}
        />
      </Campo>
      <Campo etiqueta="Formato">
        <select
          value={campo.tipo}
          disabled={!editable}
          // Al cambiar de formato el predeterminado anterior ya no sirve.
          onChange={(e) => alCambiar({ ...campo, tipo: e.target.value as TipoCampo, predeterminado: '' })}
        >
          {TIPOS.map(([valor, texto]) => (
            <option key={valor} value={valor}>
              {texto}
            </option>
          ))}
        </select>
      </Campo>
      <Campo etiqueta="Valor predeterminado">
        <input
          type={tipoDeInput(campo.tipo)}
          value={campo.predeterminado}
          maxLength={200}
          disabled={!editable}
          placeholder="Opcional"
          onChange={(e) => alCambiar({ ...campo, predeterminado: e.target.value })}
        />
      </Campo>
      {editable && (
        <Boton variante="fantasma" icono={<Trash2 className="h-4 w-4" />} onClick={alQuitar} aria-label={`Quitar ${campo.etiqueta || 'campo'}`}>
          Quitar
        </Boton>
      )}
    </li>
  )
}

/**
 * Formato del PDF de la propuesta base: logotipo, imagen al pie, título, campos extra del encabezado
 * y notas al final. Aplica a todas las propuestas; sólo un admin lo cambia.
 */
export function FormatoPdf() {
  const consulta = useAjustesPropuesta()
  const perfil = usePerfil()
  const guardar = useGuardarAjustes()
  const editable = perfil.data?.rol === 'admin'
  const [borrador, setBorrador] = useState<AjustesPropuestaEntrada | null>(null)

  // El borrador arranca de lo guardado; las imágenes se guardan al subirlas, no con este botón.
  useEffect(() => {
    if (consulta.data && borrador === null) setBorrador(entradaDe(consulta.data))
  }, [consulta.data, borrador])

  if (consulta.isLoading || !borrador) {
    return consulta.isError ? <Aviso tono="error">{mensajeDeError(consulta.error)}</Aviso> : <p className="text-texto-secundario">Cargando…</p>
  }
  const ajustes = consulta.data as AjustesPropuesta
  const cambios = JSON.stringify(borrador) !== JSON.stringify(entradaDe(ajustes))
  const camposIncompletos = borrador.campos.some((c) => !c.etiqueta.trim())
  const cambiar = (parcial: Partial<AjustesPropuestaEntrada>) => setBorrador({ ...borrador, ...parcial })
  const cambiarCampo = (indice: number, campo: CampoPropuesta) =>
    cambiar({ campos: borrador.campos.map((c, i) => (i === indice ? campo : c)) })

  return (
    <div className="pb-28">
      <header>
        <h1 className="text-3xl">Formato del PDF</h1>
        <p className="mt-1 max-w-3xl text-texto-secundario">
          Lo que lleva la propuesta base además de las partidas: logotipo, título, datos extra en el encabezado y las notas al final. Aplica
          a todas las propuestas que se generen desde ahora; la presentación editorial no cambia.
        </p>
      </header>

      {!editable && (
        <Aviso tono="info" className="mt-6">
          Sólo un administrador puede cambiar el formato del PDF. Los valores de los campos (fecha del evento, lugar…) se llenan en cada
          cotización, en Revisar.
        </Aviso>
      )}

      <section className="tarjeta mt-6 p-5" aria-labelledby="titulo-identidad">
        <h2 id="titulo-identidad" className="text-base font-semibold">
          Identidad visual
        </h2>
        <div className="mt-4 grid gap-6 md:grid-cols-2">
          <ImagenMarca
            hueco="logotipo"
            titulo="Logotipo"
            ayuda="Arriba a la izquierda, sobre el título. Mejor un PNG con fondo transparente."
            url={ajustes.logotipo_url}
            vacia={ajustes.logotipo_de_marca ? 'Logotipo de Minimal 4.0 (el de la marca)' : 'No se encontró la imagen'}
            puedeQuitar={!ajustes.logotipo_de_marca}
            etiquetaQuitar="Volver al de la marca"
            editable={editable}
          />
          <ImagenMarca
            hueco="pie"
            titulo="Imagen al pie"
            ayuda="Opcional: al final del documento, después de las notas (p. ej. datos de contacto o redes)."
            url={ajustes.pie_url}
            vacia="Sin imagen al pie"
            puedeQuitar={Boolean(ajustes.pie_ruta)}
            etiquetaQuitar="Quitar"
            editable={editable}
          />
        </div>
      </section>

      <section className="tarjeta mt-6 p-5" aria-labelledby="titulo-encabezado">
        <h2 id="titulo-encabezado" className="text-base font-semibold">
          Encabezado
        </h2>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <Campo etiqueta="Título" ayuda="Vacío = «Propuesta de mobiliario» (en inglés se traduce solo).">
            <input value={borrador.titulo} maxLength={80} disabled={!editable} placeholder="Propuesta de mobiliario" onChange={(e) => cambiar({ titulo: e.target.value })} />
          </Campo>
          <Campo etiqueta="Subtítulo" ayuda="Vacío = el lema de la marca.">
            <input
              value={borrador.subtitulo}
              maxLength={120}
              disabled={!editable}
              placeholder="Minimal 4.0 · Diseño, construcción y eventos"
              onChange={(e) => cambiar({ subtitulo: e.target.value })}
            />
          </Campo>
        </div>

        <h3 className="mt-6 text-sm font-semibold">Campos extra</h3>
        <p className="mt-1 text-sm text-texto-secundario">
          Van a la derecha, debajo de Cliente, Referencia y Fecha. El valor de cada uno se llena en cada cotización (en Revisar); si se deja
          vacío se usa el predeterminado, y si tampoco hay, el campo no se imprime.
        </p>
        {borrador.campos.length === 0 ? (
          <p className="mt-3 text-sm text-texto-secundario">No hay campos extra.</p>
        ) : (
          <ul className="mt-2 divide-y divide-borde">
            {borrador.campos.map((campo, indice) => (
              <FilaCampo
                key={campo.id}
                campo={campo}
                editable={editable}
                alCambiar={(nuevo) => cambiarCampo(indice, nuevo)}
                alQuitar={() => cambiar({ campos: borrador.campos.filter((_, i) => i !== indice) })}
              />
            ))}
          </ul>
        )}
        {editable && borrador.campos.length < 12 && (
          <Boton
            variante="secundario"
            className="mt-3"
            icono={<Plus className="h-4 w-4" />}
            onClick={() => cambiar({ campos: [...borrador.campos, { id: idNuevo(), etiqueta: '', tipo: 'texto', predeterminado: '' }] })}
          >
            Agregar campo
          </Boton>
        )}
      </section>

      <section className="tarjeta mt-6 p-5" aria-labelledby="titulo-notas">
        <h2 id="titulo-notas" className="text-base font-semibold">
          Notas al final
        </h2>
        <p className="mt-1 text-sm text-texto-secundario">Términos y condiciones, anticipos, cambios… Se imprimen tal cual, renglón por renglón.</p>
        <div className="mt-4 flex flex-col gap-4">
          <Campo etiqueta="Título de las notas" ayuda="Vacío = sin título.">
            <input value={borrador.notas_titulo} maxLength={60} disabled={!editable} onChange={(e) => cambiar({ notas_titulo: e.target.value })} />
          </Campo>
          <Campo etiqueta="Texto">
            <textarea rows={9} value={borrador.notas} maxLength={4000} disabled={!editable} onChange={(e) => cambiar({ notas: e.target.value })} />
          </Campo>
        </div>
      </section>

      {editable && (
        <div className="fixed inset-x-0 bottom-0 z-30 border-t border-borde bg-superficie/95 backdrop-blur">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-3 sm:px-6">
            <div className="text-sm">
              {guardar.isError ? (
                <span className="text-alerta-texto">{mensajeDeError(guardar.error)}</span>
              ) : camposIncompletos ? (
                <span className="text-pendiente-texto">Cada campo necesita una etiqueta.</span>
              ) : (
                <span className="text-texto-secundario">{cambios ? 'Hay cambios sin guardar.' : 'Todo guardado.'}</span>
              )}
            </div>
            <div className="flex gap-2">
              <Boton variante="fantasma" disabled={!cambios || guardar.isPending} onClick={() => setBorrador(entradaDe(ajustes))}>
                Descartar
              </Boton>
              <Boton
                icono={<Save className="h-4 w-4" />}
                disabled={!cambios || camposIncompletos}
                cargando={guardar.isPending}
                onClick={() => guardar.mutate(borrador, { onSuccess: (guardados) => setBorrador(entradaDe(guardados)) })}
              >
                Guardar cambios
              </Boton>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
