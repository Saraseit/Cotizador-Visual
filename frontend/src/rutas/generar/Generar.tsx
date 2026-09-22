import { ArrowLeft, ExternalLink, FileDown, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { useCotizacion, useGenerarPropuesta } from '@/api/consultas'
import type { ResultadoPdf } from '@/api/tipos'
import { Aviso, mensajeDeError } from '@/componentes/Aviso'
import { Boton } from '@/componentes/Boton'
import { Pildora } from '@/componentes/Pildora'
import { moneda } from '@/lib/formato'

export function Generar() {
  const { id } = useParams<{ id: string }>()
  const consulta = useCotizacion(id)
  const generar = useGenerarPropuesta(id ?? '')
  const [resultado, setResultado] = useState<ResultadoPdf | null>(null)

  const cotizacion = consulta.data
  if (consulta.isLoading) return <p className="text-texto-secundario">Cargando cotización…</p>
  if (consulta.isError || !cotizacion) {
    return <Aviso tono="error">{consulta.error ? mensajeDeError(consulta.error) : 'No se encontró la cotización.'}</Aviso>
  }

  const conceptuales = cotizacion.items.filter((i) => i.es_render_conceptual).length

  const descargar = () => {
    generar.mutate(undefined, {
      onSuccess: (pdf) => {
        setResultado(pdf)
        window.open(pdf.url, '_blank', 'noopener')
      },
    })
  }

  return (
    <div>
      <Link to={`/cotizaciones/${cotizacion.id}`} className="inline-flex items-center gap-1 text-sm text-texto-secundario hover:text-texto">
        <ArrowLeft className="h-4 w-4" /> Volver a revisar
      </Link>
      <header className="mt-3">
        <p className="text-sm text-texto-secundario">Paso 3 · Generar propuesta</p>
        <h1 className="mt-1 text-3xl">{cotizacion.nombre_cliente}</h1>
        <p className="mt-1 text-texto-secundario">
          Referencia {cotizacion.referencia_externa || 'sin referencia'} · {cotizacion.total_items} ítems · total{' '}
          {moneda(cotizacion.total)}
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          {cotizacion.items_pendientes > 0 ? (
            <Pildora tono="pendiente">{cotizacion.items_pendientes} sin imagen</Pildora>
          ) : (
            <Pildora tono="resuelto">Todos los ítems con imagen</Pildora>
          )}
          {conceptuales > 0 && <Pildora tono="conceptual">{conceptuales} render{conceptuales === 1 ? '' : 's'} conceptual{conceptuales === 1 ? '' : 'es'}</Pildora>}
        </div>
      </header>

      <div className="mt-8 grid gap-5 md:grid-cols-2">
        <section className="tarjeta flex flex-col p-6">
          <h2 className="text-xl">Formato base</h2>
          <p className="mt-2 text-sm text-texto-secundario">
            PDF tamaño carta con encabezado del cliente, tabla de partidas con miniatura, cantidades, precios unitarios e
            importes, y total al final.
            {conceptuales > 0 && ' Los renders conceptuales llevan su etiqueta y la leyenda al pie.'}
          </p>
          <div className="mt-6 flex flex-wrap items-center gap-3">
            <Boton icono={<FileDown className="h-4 w-4" />} cargando={generar.isPending} onClick={descargar}>
              Descargar propuesta
            </Boton>
            {resultado && (
              <a
                href={resultado.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex min-h-boton items-center gap-2 text-sm font-medium text-acento underline-offset-2 hover:underline"
              >
                <ExternalLink className="h-4 w-4" /> Abrir el PDF generado
              </a>
            )}
          </div>
          {generar.isPending && <p className="mt-3 text-xs text-texto-secundario">Armando el PDF, unos segundos…</p>}
          {generar.isError && (
            <Aviso tono="error" className="mt-4">
              {mensajeDeError(generar.error)}
            </Aviso>
          )}
          {resultado && (
            <p className="mt-4 text-xs text-texto-secundario">
              El enlace es temporal (10 minutos). El archivo queda guardado en Storage y se puede volver a generar en cualquier
              momento.
            </p>
          )}
        </section>

        <section className="tarjeta flex flex-col p-6">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-xl">Presentación editorial</h2>
            <Pildora tono="conceptual">Piloto</Pildora>
          </div>
          <p className="mt-2 text-sm text-texto-secundario">
            La propuesta con el diseño de Minimal 4.0: portada con foto de ambiente, una apertura por sección con su montaje
            (tuyo o generado con IA), las piezas y el concentrado al final. Puedes ocultar los precios.
          </p>
          <div className="mt-6">
            <Link
              to={`/cotizaciones/${cotizacion.id}/presentacion`}
              className="inline-flex min-h-boton items-center justify-center gap-2 rounded-boton bg-acento px-4 text-sm font-medium text-superficie transition-colors hover:bg-acento-oscuro"
            >
              <Sparkles className="h-4 w-4" /> Armar la presentación
            </Link>
          </div>
        </section>
      </div>
    </div>
  )
}
