import { ArrowLeft, ExternalLink, FileDown, ImagePlus, Languages, Sparkles } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import {
  useCotizacion,
  useGenerarMontaje,
  useGenerarPdfPresentacion,
  useGuardarPresentacion,
  usePresentacion,
  useTraducirPresentacion,
} from '@/api/consultas'
import type {
  Composicion,
  ConfigPresentacionEntrada,
  Imagen,
  ParametrosPlantilla,
  PiezasPorPagina,
  Presentacion as PresentacionDatos,
  ResultadoPdf,
  SeccionVista,
} from '@/api/tipos'
import { Aviso, mensajeDeError } from '@/componentes/Aviso'
import { Boton } from '@/componentes/Boton'
import { Campo, Chip } from '@/componentes/Campo'
import { Pildora } from '@/componentes/Pildora'
import { moneda } from '@/lib/formato'

import { SelectorImagenHueco } from './SelectorImagenHueco'
import { SelectorPaleta } from './SelectorPaleta'
import { NOMBRE_COMPOSICION, SelectorPlantilla } from './SelectorPlantilla'

const COMPOSICIONES = Object.keys(NOMBRE_COMPOSICION) as Composicion[]
const PIEZAS_POR_PAGINA: PiezasPorPagina[] = [1, 2, 4, 6]

const HUECOS_AMBIENTACION = [
  { hueco: 'portada', titulo: 'Portada', ayuda: 'La foto grande de la primera página.' },
  { hueco: 'manifiesto', titulo: 'Manifiesto', ayuda: 'Foto a página completa con las frases de la marca.' },
  { hueco: 'cierre', titulo: 'Cierre', ayuda: 'Foto de ambiente antes del concentrado. Opcional.' },
]

const entrada = (datos: PresentacionDatos): ConfigPresentacionEntrada => ({
  brief: datos.config.brief,
  titulo: datos.config.titulo,
  evento: datos.config.evento,
  plantilla_id: datos.config.plantilla_id,
  parametros: { ...datos.config.parametros, paleta: { ...datos.config.parametros.paleta } },
  mostrar_precios: datos.config.mostrar_precios,
  moneda: datos.config.moneda,
  tipo_cambio: datos.config.tipo_cambio,
  idioma: datos.config.idioma,
  manifiesto: [...datos.config.manifiesto],
  cierre: [...datos.config.cierre],
  // Las secciones que manda el servidor son las de la cotización, con lo ya configurado.
  secciones: datos.secciones.map((s) => ({ clave: s.clave, titulo: s.titulo, texto: s.texto, incluir: s.incluir })),
})

function TarjetaHueco({
  titulo,
  ayuda,
  imagen,
  etiqueta,
  alElegir,
}: {
  titulo: string
  ayuda: string
  imagen: Imagen | undefined
  etiqueta?: string
  alElegir: () => void
}) {
  return (
    <div className="tarjeta overflow-hidden">
      <button
        type="button"
        onClick={alElegir}
        className="relative block aspect-[4/3] w-full bg-fondo transition-opacity hover:opacity-90"
        aria-label={`Elegir imagen de ${titulo}`}
      >
        {imagen?.url ? (
          <img src={imagen.url} alt="" className="h-full w-full object-cover" />
        ) : (
          <span className="flex h-full flex-col items-center justify-center gap-2 text-sm text-texto-secundario">
            <ImagePlus className="h-6 w-6" />
            Elegir imagen
          </span>
        )}
        {etiqueta && (
          <span className="absolute left-2 top-2">
            <Pildora tono="conceptual">{etiqueta}</Pildora>
          </span>
        )}
      </button>
      <div className="p-3">
        <p className="text-sm font-medium">{titulo}</p>
        <p className="text-xs text-texto-secundario">{ayuda}</p>
        <Boton variante="secundario" className="mt-3 w-full" onClick={alElegir}>
          {imagen ? 'Cambiar' : 'Elegir'}
        </Boton>
      </div>
    </div>
  )
}

export function Presentacion() {
  const { id = '' } = useParams<{ id: string }>()
  const cotizacion = useCotizacion(id)
  const consulta = usePresentacion(id)
  const guardar = useGuardarPresentacion(id)
  const generarMontaje = useGenerarMontaje(id)
  const generarPdf = useGenerarPdfPresentacion(id)
  const traducir = useTraducirPresentacion(id)

  const [borrador, setBorrador] = useState<ConfigPresentacionEntrada | null>(null)
  const [guardado, setGuardado] = useState('')
  const [hueco, setHueco] = useState<{ hueco: string; titulo: string; clave: string | null } | null>(null)
  const [pdf, setPdf] = useState<ResultadoPdf | null>(null)
  const [enLote, setEnLote] = useState<{ hechos: number; total: number } | null>(null)

  const datos = consulta.data
  useEffect(() => {
    if (!datos || borrador) return
    const inicial = entrada(datos)
    setBorrador(inicial)
    setGuardado(JSON.stringify(inicial))
  }, [datos, borrador])

  const sucio = useMemo(() => Boolean(borrador) && JSON.stringify(borrador) !== guardado, [borrador, guardado])

  if (consulta.isLoading || cotizacion.isLoading) return <p className="text-texto-secundario">Cargando presentación…</p>
  if (consulta.isError || !datos || !cotizacion.data) {
    return (
      <Aviso tono="error">
        {consulta.error ? mensajeDeError(consulta.error) : 'No se encontró la cotización.'}{' '}
        <Link to="/" className="underline">
          Volver
        </Link>
      </Aviso>
    )
  }
  if (!borrador) return <p className="text-texto-secundario">Cargando presentación…</p>

  const cambiar = (cambios: Partial<ConfigPresentacionEntrada>) => setBorrador({ ...borrador, ...cambios })
  const parametros = borrador.parametros
  const cambiarParametros = (cambios: Partial<ParametrosPlantilla>) =>
    setBorrador({ ...borrador, parametros: { ...borrador.parametros, ...cambios } })
  const traducidos = Object.keys(datos.config.traducciones ?? {}).length
  const cambiarSeccion = (clave: string, cambios: Partial<SeccionVista>) =>
    setBorrador({
      ...borrador,
      secciones: borrador.secciones.map((s) => (s.clave === clave ? { ...s, ...cambios } : s)),
    })

  const guardarAhora = async () => {
    if (!sucio) return
    const texto = JSON.stringify(borrador)
    await guardar.mutateAsync(borrador)
    setGuardado(texto)
  }

  const traducirAhora = async () => {
    await guardarAhora() // la IA traduce lo que ya está guardado
    await traducir.mutateAsync()
  }

  const generarUno = async (clave: string) => {
    await guardarAhora() // el backend arma el prompt con lo último guardado
    await generarMontaje.mutateAsync({ clave })
  }

  const generarFaltantes = async () => {
    const pendientes = datos.secciones.filter((s) => s.incluir && !datos.config.imagenes[`montaje:${s.clave}`])
    setEnLote({ hechos: 0, total: pendientes.length })
    try {
      await guardarAhora()
      for (const [indice, seccion] of pendientes.entries()) {
        await generarMontaje.mutateAsync({ clave: seccion.clave })
        setEnLote({ hechos: indice + 1, total: pendientes.length })
      }
    } finally {
      setEnLote(null)
    }
  }

  const generarElPdf = async () => {
    await guardarAhora()
    const resultado = await generarPdf.mutateAsync()
    setPdf(resultado)
  }

  const faltanMontajes = datos.secciones.filter((s) => s.incluir && !datos.config.imagenes[`montaje:${s.clave}`]).length
  const ocupado = guardar.isPending || generarMontaje.isPending || generarPdf.isPending || traducir.isPending
  const error = guardar.error ?? generarMontaje.error ?? generarPdf.error ?? traducir.error

  return (
    <div className="pb-28">
      <Link to={`/cotizaciones/${id}/generar`} className="inline-flex items-center gap-1 text-sm text-texto-secundario hover:text-texto">
        <ArrowLeft className="h-4 w-4" /> Volver a generar
      </Link>
      <header className="mt-3">
        <p className="text-sm text-texto-secundario">Paso 3 · Presentación editorial</p>
        <h1 className="mt-1 text-3xl">{cotizacion.data.nombre_cliente}</h1>
        <p className="mt-1 text-texto-secundario">
          {datos.secciones.length} {datos.secciones.length === 1 ? 'sección' : 'secciones'} · {cotizacion.data.total_items} partidas · total{' '}
          {moneda(cotizacion.data.total)}
          {cotizacion.data.iva === null && ' más IVA'}
        </p>
      </header>

      {error && (
        <Aviso tono="error" className="mt-4">
          {mensajeDeError(error)}
        </Aviso>
      )}

      <div className="mt-8 grid gap-8 xl:grid-cols-[minmax(0,1fr)_30rem]">
        <div className="space-y-8">
          <section className="tarjeta p-5">
            <h2 className="text-xl">Indicaciones</h2>
            <p className="mt-1 text-sm text-texto-secundario">
              Cuenta cómo es el evento y cómo quieres la presentación. Esto es lo que la IA usa para los montajes.
            </p>
            <Campo etiqueta="Indicaciones para esta propuesta" className="mt-4">
              <textarea
                rows={4}
                value={borrador.brief}
                onChange={(evento) => cambiar({ brief: evento.target.value })}
                placeholder="Boda al atardecer en hacienda, tonos chocolate y lino crudo, mucha vela. Destacar el lounge."
              />
            </Campo>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <Campo etiqueta="Título de la portada">
                <input value={borrador.titulo} maxLength={40} onChange={(evento) => cambiar({ titulo: evento.target.value })} />
              </Campo>
              <Campo etiqueta="Evento o cliente" ayuda="Aparece en la portada y en el concentrado.">
                <input value={borrador.evento} maxLength={80} onChange={(evento) => cambiar({ evento: evento.target.value })} />
              </Campo>
            </div>
          </section>

          <SelectorPlantilla
            plantillaId={borrador.plantilla_id}
            alAplicar={(plantilla) =>
              cambiar({
                plantilla_id: plantilla.id,
                parametros: { ...plantilla.parametros, paleta: { ...plantilla.parametros.paleta } },
              })
            }
          />

          <section className="tarjeta p-5">
            <h2 className="text-xl">Ajustes del diseño</h2>
            <p className="mt-1 text-sm text-texto-secundario">
              Salen de la plantilla y los puedes mover aquí sin cambiarla. El logotipo, las tipografías de marca y el verde no se tocan.
            </p>

            <p className="mt-4 text-sm font-medium">Composición</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {COMPOSICIONES.map((valor) => (
                <Chip key={valor} activo={parametros.composicion === valor} onClick={() => cambiarParametros({ composicion: valor })}>
                  {NOMBRE_COMPOSICION[valor]}
                </Chip>
              ))}
            </div>

            <p className="mt-5 text-sm font-medium">Tipografía de los títulos</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {(
                [
                  ['everett', 'Everett'],
                  ['bebas', 'Bebas Neue'],
                ] as const
              ).map(([valor, nombre]) => (
                <Chip
                  key={valor}
                  activo={parametros.tipografia_titulos === valor}
                  onClick={() => cambiarParametros({ tipografia_titulos: valor })}
                >
                  {nombre}
                </Chip>
              ))}
            </div>

            <p className="mt-5 text-sm font-medium">Piezas por página</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {PIEZAS_POR_PAGINA.map((valor) => (
                <Chip
                  key={valor}
                  activo={parametros.piezas_por_pagina === valor}
                  onClick={() => cambiarParametros({ piezas_por_pagina: valor })}
                >
                  {valor}
                </Chip>
              ))}
            </div>

            <Campo
              etiqueta={`Tamaño de los títulos (${parametros.escala_titulos.toFixed(2)})`}
              ayuda="1.00 llena el ancho de la página; menos, títulos más discretos."
              className="mt-5"
            >
              <input
                type="range"
                min={0.5}
                max={1.4}
                step={0.05}
                value={parametros.escala_titulos}
                onChange={(evento) => cambiarParametros({ escala_titulos: Number(evento.target.value) })}
              />
            </Campo>

            <div className="mt-4 space-y-2">
              {(
                [
                  ['fotos_a_sangre', 'Fotos hasta el borde de la página'],
                  ['mostrar_manifiesto', 'Incluir la página del manifiesto'],
                  ['mostrar_cierre', 'Incluir la página de cierre'],
                ] as const
              ).map(([campo, etiqueta]) => (
                <label key={campo} className="flex items-center gap-3 text-sm font-medium">
                  <input
                    type="checkbox"
                    className="h-4 w-4"
                    checked={parametros[campo]}
                    onChange={(evento) => cambiarParametros({ [campo]: evento.target.checked } as Partial<ParametrosPlantilla>)}
                  />
                  {etiqueta}
                </label>
              ))}
            </div>

            <div className="mt-5">
              <SelectorPaleta paleta={parametros.paleta} alCambiar={(paleta) => cambiarParametros({ paleta })} />
            </div>
          </section>

          <section className="tarjeta p-5">
            <h2 className="text-xl">Precios, moneda e idioma</h2>

            <label className="mt-4 flex items-center gap-3 text-sm font-medium">
              <input
                type="checkbox"
                className="h-4 w-4"
                checked={borrador.mostrar_precios}
                onChange={(evento) => cambiar({ mostrar_precios: evento.target.checked })}
              />
              Mostrar precios del mobiliario
            </label>
            <p className="ml-7 text-xs text-texto-secundario">
              Sin precios, las piezas salen sólo con cantidad y el concentrado final no lleva importes.
            </p>

            <p className="mt-5 text-sm font-medium">Moneda</p>
            <div className="mt-2 flex flex-wrap items-end gap-3">
              {(
                [
                  ['MXN', 'Pesos'],
                  ['USD', 'Dólares'],
                ] as const
              ).map(([valor, nombre]) => (
                <Chip
                  key={valor}
                  activo={borrador.moneda === valor}
                  onClick={() =>
                    cambiar({ moneda: valor, tipo_cambio: valor === 'USD' ? (borrador.tipo_cambio ?? 18) : borrador.tipo_cambio })
                  }
                >
                  {nombre}
                </Chip>
              ))}
              {borrador.moneda === 'USD' && (
                <Campo etiqueta="Tipo de cambio" ayuda="Pesos por dólar. Se imprime al pie de la propuesta.">
                  <input
                    type="number"
                    min={1}
                    max={1000}
                    step={0.01}
                    className="w-32"
                    value={borrador.tipo_cambio ?? ''}
                    onChange={(evento) => cambiar({ tipo_cambio: evento.target.value ? Number(evento.target.value) : null })}
                  />
                </Campo>
              )}
            </div>
            {borrador.moneda === 'USD' && !borrador.tipo_cambio && (
              <Aviso tono="error" className="mt-3">
                Pon el tipo de cambio para poder guardar en dólares.
              </Aviso>
            )}

            <p className="mt-5 text-sm font-medium">Idioma de la propuesta</p>
            <div className="mt-2 flex flex-wrap items-center gap-3">
              {(
                [
                  ['es', 'Español'],
                  ['en', 'Inglés'],
                ] as const
              ).map(([valor, nombre]) => (
                <Chip key={valor} activo={borrador.idioma === valor} onClick={() => cambiar({ idioma: valor })}>
                  {nombre}
                </Chip>
              ))}
              {borrador.idioma !== 'es' && (
                <Boton
                  variante="secundario"
                  icono={<Languages className="h-4 w-4" />}
                  cargando={traducir.isPending}
                  disabled={ocupado}
                  onClick={() => void traducirAhora()}
                >
                  Traducir con IA
                </Boton>
              )}
            </div>
            <p className="mt-2 text-xs text-texto-secundario">
              En inglés se traducen los textos y las medidas pasan a pies y pulgadas. Lo que hayas escrito a mano en la descripción de una
              partida se imprime tal cual. La traducción se guarda: sólo se paga una vez.
            </p>
            {traducidos > 0 && <p className="mt-1 text-xs text-texto-secundario">{traducidos} textos ya traducidos.</p>}
          </section>

          <section className="tarjeta p-5">
            <h2 className="text-xl">Imágenes de ambientación</h2>
            <p className="mt-1 text-sm text-texto-secundario">
              Fotos de ambiente para la portada y las páginas de marca. Se guardan en una biblioteca común.
            </p>
            <div className="mt-4 grid gap-4 sm:grid-cols-3">
              {HUECOS_AMBIENTACION.map((item) => (
                <TarjetaHueco
                  key={item.hueco}
                  titulo={item.titulo}
                  ayuda={item.ayuda}
                  imagen={datos.imagenes[item.hueco]}
                  alElegir={() => setHueco({ hueco: item.hueco, titulo: `Imagen de ${item.titulo.toLowerCase()}`, clave: null })}
                />
              ))}
            </div>
          </section>

          <section className="tarjeta p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-xl">Secciones</h2>
              {faltanMontajes > 0 && (
                <Boton
                  variante="secundario"
                  icono={<Sparkles className="h-4 w-4" />}
                  cargando={Boolean(enLote)}
                  disabled={ocupado}
                  onClick={generarFaltantes}
                >
                  {enLote ? `Generando ${enLote.hechos + 1} de ${enLote.total}…` : `Generar los ${faltanMontajes} montajes que faltan`}
                </Boton>
              )}
            </div>
            <p className="mt-1 text-sm text-texto-secundario">
              Cada sección abre con su montaje y un texto tuyo, y después van sus piezas.
            </p>

            <div className="mt-4 space-y-4">
              {datos.secciones.map((seccion) => {
                const ajuste = borrador.secciones.find((s) => s.clave === seccion.clave)
                if (!ajuste) return null
                const imagen = datos.imagenes[`montaje:${seccion.clave}`]
                return (
                  <div key={seccion.clave} className="rounded-tarjeta border border-borde p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-xs uppercase tracking-wide text-texto-secundario">{seccion.categoria || 'Sin sección'}</p>
                        <p className="mt-1 text-sm text-texto-secundario">
                          {seccion.partidas} partidas · {seccion.con_imagen} con foto · {moneda(seccion.importe)}
                        </p>
                      </div>
                      <label className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          className="h-4 w-4"
                          checked={ajuste.incluir}
                          onChange={(evento) => cambiarSeccion(seccion.clave, { incluir: evento.target.checked })}
                        />
                        Incluir en la presentación
                      </label>
                    </div>

                    <div className="mt-4 grid gap-4 md:grid-cols-[1fr_16rem]">
                      <div className="space-y-3">
                        <Campo etiqueta="Título editorial">
                          <input
                            value={ajuste.titulo}
                            maxLength={40}
                            onChange={(evento) => cambiarSeccion(seccion.clave, { titulo: evento.target.value })}
                          />
                        </Campo>
                        <Campo etiqueta="Texto" ayuda="Deja un renglón en blanco entre párrafos: van en tres columnas.">
                          <textarea
                            rows={4}
                            value={ajuste.texto}
                            maxLength={900}
                            onChange={(evento) => cambiarSeccion(seccion.clave, { texto: evento.target.value })}
                            placeholder="Una combinación de colores que enmarcan la calidez del ambiente."
                          />
                        </Campo>
                      </div>
                      <div className="space-y-2">
                        <TarjetaHueco
                          titulo="Montaje"
                          ayuda={seccion.con_imagen > 0 ? `${seccion.con_imagen} fotos de referencia` : 'Sin fotos de referencia'}
                          imagen={imagen}
                          etiqueta={imagen?.tipo === 'montaje' ? 'IA' : undefined}
                          alElegir={() =>
                            setHueco({ hueco: `montaje:${seccion.clave}`, titulo: `Montaje de ${ajuste.titulo}`, clave: seccion.clave })
                          }
                        />
                        {!imagen && (
                          <Boton
                            variante="secundario"
                            className="w-full"
                            icono={<Sparkles className="h-4 w-4" />}
                            disabled={ocupado || Boolean(enLote)}
                            onClick={() => void generarUno(seccion.clave)}
                          >
                            Generar con IA
                          </Boton>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </section>

          <details className="tarjeta p-5">
            <summary className="cursor-pointer text-xl">Textos de marca</summary>
            <p className="mt-2 text-sm text-texto-secundario">
              Las tres columnas de la página del manifiesto y de la de cierre. Cada renglón sale como renglón.
            </p>
            {(
              [
                ['manifiesto', 'Manifiesto'],
                ['cierre', 'Cierre'],
              ] as const
            ).map(([campo, etiqueta]) => (
              <div key={campo} className="mt-4">
                <p className="text-sm font-medium">{etiqueta}</p>
                <div className="mt-2 grid gap-3 sm:grid-cols-3">
                  {[0, 1, 2].map((indice) => (
                    <textarea
                      key={indice}
                      rows={3}
                      value={borrador[campo][indice] ?? ''}
                      onChange={(evento) => {
                        const textos = [...borrador[campo]]
                        textos[indice] = evento.target.value
                        cambiar({ [campo]: textos } as Partial<ConfigPresentacionEntrada>)
                      }}
                    />
                  ))}
                </div>
              </div>
            ))}
          </details>
        </div>

        <aside className="xl:sticky xl:top-6 xl:self-start">
          <section className="tarjeta p-5">
            <h2 className="text-xl">Vista previa</h2>
            <p className="mt-1 text-sm text-texto-secundario">
              Genera el PDF para verlo. Cada vez que lo generas se guarda una copia en la cotización.
            </p>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <Boton icono={<FileDown className="h-4 w-4" />} cargando={generarPdf.isPending} disabled={ocupado} onClick={generarElPdf}>
                Generar PDF
              </Boton>
              {pdf && (
                <a
                  href={pdf.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex min-h-boton items-center gap-2 text-sm font-medium text-acento underline-offset-2 hover:underline"
                >
                  <ExternalLink className="h-4 w-4" /> Abrir en una pestaña
                </a>
              )}
            </div>
            {pdf ? (
              <iframe src={pdf.url} title="Presentación" className="mt-4 h-[36rem] w-full rounded-tarjeta border border-borde" />
            ) : (
              <div className="mt-4 flex h-[36rem] items-center justify-center rounded-tarjeta border border-dashed border-borde text-sm text-texto-secundario">
                Aquí aparece la presentación
              </div>
            )}
          </section>
        </aside>
      </div>

      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-borde bg-superficie/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <p className="text-sm text-texto-secundario">
            {sucio ? 'Hay cambios sin guardar.' : datos.guardada ? 'Todo guardado.' : 'Presentación nueva: se guarda al generar el PDF.'}
          </p>
          <div className="flex items-center gap-3">
            <Boton variante="secundario" cargando={guardar.isPending} disabled={!sucio || ocupado} onClick={() => void guardarAhora()}>
              Guardar
            </Boton>
            <Boton icono={<FileDown className="h-4 w-4" />} cargando={generarPdf.isPending} disabled={ocupado} onClick={generarElPdf}>
              Generar PDF
            </Boton>
          </div>
        </div>
      </div>

      {hueco && (
        <SelectorImagenHueco
          cotizacionId={id}
          hueco={hueco.hueco}
          titulo={hueco.titulo}
          claveSeccion={hueco.clave}
          imagenActual={datos.imagenes[hueco.hueco] ?? null}
          alCerrar={() => setHueco(null)}
        />
      )}
    </div>
  )
}
