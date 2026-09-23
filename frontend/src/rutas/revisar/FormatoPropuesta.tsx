import { Languages } from 'lucide-react'
import { useState } from 'react'

import { useGuardarFormato, useTraducirPresentacion } from '@/api/consultas'
import type { ConfigPresentacion, FormatoPropuesta as Formato, Idioma, Moneda } from '@/api/tipos'
import { Aviso, mensajeDeError } from '@/componentes/Aviso'
import { Boton } from '@/componentes/Boton'
import { Campo, Chip } from '@/componentes/Campo'

const TIPO_CAMBIO_POR_DEFECTO = 18

/**
 * Moneda e idioma de los dos PDF, aquí mismo en Revisar: el vendedor ve los importes convertidos y
 * los textos traducidos en la tabla antes de imprimir, y corrige lo que haga falta sin salir.
 */
export function FormatoPropuesta({ cotizacionId, config }: { cotizacionId: string; config: ConfigPresentacion }) {
  const guardar = useGuardarFormato(cotizacionId)
  const traducir = useTraducirPresentacion(cotizacionId)
  const [tipoCambio, setTipoCambio] = useState<string>(config.tipo_cambio ? String(config.tipo_cambio) : '')

  const ocupado = guardar.isPending || traducir.isPending
  const error = guardar.error ?? traducir.error
  const traducidos = Object.keys(config.traducciones ?? {}).length

  const aplicar = (cambios: Partial<Formato>) => {
    const formato: Formato = {
      moneda: config.moneda,
      tipo_cambio: config.tipo_cambio,
      idioma: config.idioma,
      ...cambios,
    }
    if (formato.moneda === 'USD' && !formato.tipo_cambio) formato.tipo_cambio = TIPO_CAMBIO_POR_DEFECTO
    if (formato.moneda === 'USD') setTipoCambio(String(formato.tipo_cambio))
    guardar.mutate(formato)
  }

  const guardarTipoCambio = () => {
    const valor = Number(tipoCambio)
    if (!valor || valor === config.tipo_cambio) return
    aplicar({ tipo_cambio: valor })
  }

  return (
    <section className="tarjeta p-5" aria-label="Moneda e idioma de la propuesta">
      <h2 className="text-base font-semibold">Moneda e idioma</h2>
      <p className="mt-1 text-sm text-texto-secundario">
        Así saldrán los dos PDF, el base y la presentación. Los importes de esta tabla ya muestran la conversión.
      </p>

      {error && (
        <Aviso tono="error" className="mt-3">
          {mensajeDeError(error)}
        </Aviso>
      )}

      <div className="mt-4 flex flex-wrap items-end gap-3">
        {(
          [
            ['MXN', 'Pesos'],
            ['USD', 'Dólares'],
          ] as [Moneda, string][]
        ).map(([valor, nombre]) => (
          <Chip key={valor} activo={config.moneda === valor} onClick={() => !ocupado && aplicar({ moneda: valor })}>
            {nombre}
          </Chip>
        ))}
        {config.moneda === 'USD' && (
          <Campo etiqueta="Tipo de cambio" ayuda="Pesos por dólar. Se imprime al pie.">
            <input
              type="number"
              min={1}
              max={1000}
              step={0.01}
              className="w-32"
              value={tipoCambio}
              disabled={ocupado}
              onChange={(evento) => setTipoCambio(evento.target.value)}
              onBlur={guardarTipoCambio}
              onKeyDown={(evento) => evento.key === 'Enter' && guardarTipoCambio()}
            />
          </Campo>
        )}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        {(
          [
            ['es', 'Español'],
            ['en', 'Inglés'],
          ] as [Idioma, string][]
        ).map(([valor, nombre]) => (
          <Chip key={valor} activo={config.idioma === valor} onClick={() => !ocupado && aplicar({ idioma: valor })}>
            {nombre}
          </Chip>
        ))}
        {config.idioma !== 'es' && (
          <Boton
            variante="secundario"
            icono={<Languages className="h-4 w-4" />}
            cargando={traducir.isPending}
            disabled={ocupado}
            onClick={() => traducir.mutate(undefined)}
          >
            {traducidos > 0 ? 'Volver a traducir' : 'Traducir con IA'}
          </Boton>
        )}
      </div>

      {config.idioma !== 'es' && (
        <p className="mt-3 text-xs text-texto-secundario">
          Debajo de cada descripción sale su traducción. Si alguna no te gusta, edita la descripción: lo que escribas se imprime tal cual.
          Las medidas pasan a pies y pulgadas.
        </p>
      )}
    </section>
  )
}
