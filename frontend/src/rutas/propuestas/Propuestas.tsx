import { ChevronDown, Download, ExternalLink, FileText, Search, Sparkles } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { useCotizaciones, usePdfsCotizacion } from '@/api/consultas'
import type { CotizacionResumen, PdfGenerado } from '@/api/tipos'
import { Aviso, mensajeDeError } from '@/componentes/Aviso'
import { Boton } from '@/componentes/Boton'
import { PildoraEstadoCotizacion } from '@/componentes/Pildora'
import { fechaHora } from '@/lib/formato'

type Filtro = 'todas' | 'revision' | 'generada'

const ETIQUETA_TIPO: Record<PdfGenerado['tipo'], string> = {
  base: 'Propuesta',
  editorial: 'Presentación editorial',
}

function FilaPdf({ pdf }: { pdf: PdfGenerado }) {
  return (
    <li className="flex flex-wrap items-center gap-x-4 gap-y-2 py-3">
      <div className="flex min-w-0 flex-1 items-center gap-2">
        <FileText className="h-4 w-4 shrink-0 text-texto-secundario" aria-hidden />
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">{ETIQUETA_TIPO[pdf.tipo]}</p>
          <p className="text-xs text-texto-secundario">Generado el {fechaHora(pdf.creado_en)}</p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        {pdf.url ? (
          <a
            href={pdf.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex min-h-boton items-center gap-1.5 rounded-boton border border-borde px-3 text-sm font-medium text-texto hover:border-texto-secundario"
          >
            <ExternalLink className="h-4 w-4" /> Abrir para imprimir
          </a>
        ) : (
          <span className="text-sm text-texto-secundario">Ya no está disponible</span>
        )}
        {pdf.url_descarga && (
          <a
            href={pdf.url_descarga}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex min-h-boton items-center gap-1.5 rounded-boton px-3 text-sm font-medium text-texto-secundario hover:bg-fondo hover:text-texto"
          >
            <Download className="h-4 w-4" /> Descargar
          </a>
        )}
      </div>
    </li>
  )
}

function PanelPdfs({ cotizacionId, estado }: { cotizacionId: string; estado: CotizacionResumen['estado'] }) {
  const consulta = usePdfsCotizacion(cotizacionId)

  return (
    <div className="border-t border-borde bg-fondo/50 px-5 py-4">
      {consulta.isLoading && <p className="text-sm text-texto-secundario">Cargando PDF…</p>}
      {consulta.isError && <Aviso tono="error">{mensajeDeError(consulta.error)}</Aviso>}
      {consulta.data && consulta.data.length === 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-texto-secundario">
            {estado === 'revision'
              ? 'Todavía no se genera ningún PDF: faltan pasos en la revisión.'
              : 'Todavía no se genera ningún PDF para esta cotización.'}
          </p>
          <Link to={`/cotizaciones/${cotizacionId}`}>
            <Boton variante="secundario">Continuar cotización</Boton>
          </Link>
        </div>
      )}
      {consulta.data && consulta.data.length > 0 && (
        <ul className="divide-y divide-borde">
          {consulta.data.map((pdf) => (
            <FilaPdf key={pdf.id} pdf={pdf} />
          ))}
        </ul>
      )}
    </div>
  )
}

export function Propuestas() {
  const consulta = useCotizaciones()
  const [busqueda, setBusqueda] = useState('')
  const [filtro, setFiltro] = useState<Filtro>('todas')
  const [expandidas, setExpandidas] = useState<Set<string>>(new Set())

  const alternar = (id: string) =>
    setExpandidas((previo) => {
      const siguiente = new Set(previo)
      siguiente.has(id) ? siguiente.delete(id) : siguiente.add(id)
      return siguiente
    })

  const todas = consulta.data ?? []
  const conteos = useMemo(
    () => ({
      todas: todas.length,
      revision: todas.filter((c) => c.estado === 'revision').length,
      generada: todas.filter((c) => c.estado === 'generada').length,
    }),
    [todas],
  )

  const filas = useMemo(() => {
    const termino = busqueda.trim().toLowerCase()
    return todas.filter((c) => {
      if (filtro !== 'todas' && c.estado !== filtro) return false
      if (!termino) return true
      return c.nombre_cliente.toLowerCase().includes(termino) || c.referencia_externa.toLowerCase().includes(termino)
    })
  }, [todas, filtro, busqueda])

  return (
    <div>
      <header>
        <h1 className="text-3xl">Propuestas</h1>
        <p className="mt-1 text-texto-secundario">
          Todas las cotizaciones y los PDF que se han generado de cada una: la propuesta base y, si se hizo, la presentación editorial.
          Ábrelos para imprimir o descárgalos.
        </p>
      </header>

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1" role="tablist" aria-label="Filtro de propuestas">
          {(
            [
              ['todas', `Todas (${conteos.todas})`],
              ['revision', `En revisión (${conteos.revision})`],
              ['generada', `Generadas (${conteos.generada})`],
            ] as const
          ).map(([valor, texto]) => (
            <button
              key={valor}
              type="button"
              role="tab"
              aria-selected={filtro === valor}
              onClick={() => setFiltro(valor)}
              className={`min-h-boton rounded-pildora border px-4 text-sm font-medium transition-colors ${
                filtro === valor
                  ? 'border-texto bg-texto text-superficie'
                  : 'border-borde bg-superficie text-texto-secundario hover:text-texto'
              }`}
            >
              {texto}
            </button>
          ))}
        </div>
        <div className="relative ml-auto w-full max-w-xs">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-texto-secundario" />
          <input
            value={busqueda}
            onChange={(evento) => setBusqueda(evento.target.value)}
            placeholder="Buscar por cliente o referencia…"
            className="w-full pl-9"
            aria-label="Buscar propuestas"
          />
        </div>
      </div>

      <div className="tarjeta mt-4 divide-y divide-borde overflow-hidden">
        {consulta.isLoading && <p className="p-5 text-sm text-texto-secundario">Cargando…</p>}
        {consulta.isError && (
          <div className="p-5">
            <Aviso tono="error">{mensajeDeError(consulta.error)}</Aviso>
          </div>
        )}
        {consulta.data?.length === 0 && (
          <div className="p-5 text-sm text-texto-secundario">
            Todavía no hay propuestas.{' '}
            <Link to="/" className="underline">
              Sube tu primer export
            </Link>
            .
          </div>
        )}
        {consulta.data && consulta.data.length > 0 && filas.length === 0 && (
          <p className="p-5 text-sm text-texto-secundario">Ninguna propuesta coincide con la búsqueda o el filtro.</p>
        )}
        {filas.map((cotizacion) => {
          const abierta = expandidas.has(cotizacion.id)
          return (
            <div key={cotizacion.id}>
              <button
                type="button"
                onClick={() => alternar(cotizacion.id)}
                aria-expanded={abierta}
                className="flex w-full flex-wrap items-center gap-x-6 gap-y-2 px-5 py-4 text-left hover:bg-fondo/60"
              >
                <ChevronDown className={`h-4 w-4 shrink-0 text-texto-secundario transition-transform ${abierta ? 'rotate-180' : ''}`} />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{cotizacion.nombre_cliente || 'Cliente sin nombre'}</p>
                  <p className="text-sm text-texto-secundario">
                    {cotizacion.referencia_externa || 'Sin referencia'} · {fechaHora(cotizacion.creado_en)} · {cotizacion.total_items} ítems
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  {cotizacion.items_pendientes > 0 && (
                    <span className="text-sm text-pendiente-texto">{cotizacion.items_pendientes} sin imagen</span>
                  )}
                  <PildoraEstadoCotizacion estado={cotizacion.estado} />
                </div>
              </button>
              {abierta && <PanelPdfs cotizacionId={cotizacion.id} estado={cotizacion.estado} />}
            </div>
          )
        })}
      </div>

      <p className="mt-4 flex items-center gap-2 text-sm text-texto-secundario">
        <Sparkles className="h-4 w-4" />
        La presentación editorial se arma desde Generar, dentro de cada cotización.
      </p>
    </div>
  )
}
