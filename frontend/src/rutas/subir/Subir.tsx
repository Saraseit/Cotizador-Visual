import { ArrowRight } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { useCotizaciones, useCrearCotizacion } from '@/api/consultas'
import { Aviso, mensajeDeError } from '@/componentes/Aviso'
import { Boton } from '@/componentes/Boton'
import { PildoraEstadoCotizacion } from '@/componentes/Pildora'
import { ZonaArrastre } from '@/componentes/ZonaArrastre'
import { fecha } from '@/lib/formato'

export function Subir() {
  const navegar = useNavigate()
  const crear = useCrearCotizacion()
  const recientes = useCotizaciones()
  const [error, setError] = useState<string | null>(null)

  const alSeleccionar = (archivo: File) => {
    setError(null)
    // El PDF es la única entrada: trae cliente, referencia y datos del evento que el Excel no incluye.
    // El atributo accept no cubre el arrastrar y soltar, así que se revisa aquí también.
    if (!archivo.name.toLowerCase().endsWith('.pdf')) {
      setError(
        'La propuesta se arma con el PDF de la cotización, no con el Excel: solo el PDF trae el cliente, ' +
          'el número de cotización y los datos del evento. Expórtalo desde el sistema y vuelve a subirlo.',
      )
      return
    }
    crear.mutate(archivo, {
      onSuccess: (detalle) => navegar(`/cotizaciones/${detalle.id}`),
      onError: (fallo) => setError(mensajeDeError(fallo)),
    })
  }

  return (
    <div className="flex flex-col gap-10">
      <section>
        <h1 className="text-3xl">Nueva propuesta</h1>
        <p className="mt-1 text-texto-secundario">
          Sube el PDF de la cotización del sistema. Resolvemos las imágenes del catálogo automáticamente y tú ajustas
          el resto.
        </p>
        <div className="mt-6">
          <ZonaArrastre alSeleccionar={alSeleccionar} ocupado={crear.isPending} />
        </div>
        {error && (
          <Aviso tono="error" className="mt-4">
            {error}
          </Aviso>
        )}
      </section>

      <section>
        <div className="flex items-baseline justify-between">
          <h2 className="text-xl">Propuestas recientes</h2>
          {recientes.data && <span className="text-sm text-texto-secundario">{recientes.data.length} en total</span>}
        </div>

        <div className="tarjeta mt-4 divide-y divide-borde">
          {recientes.isLoading && <p className="p-5 text-sm text-texto-secundario">Cargando…</p>}
          {recientes.isError && (
            <div className="p-5">
              <Aviso tono="error">{mensajeDeError(recientes.error)}</Aviso>
            </div>
          )}
          {recientes.data?.length === 0 && (
            <p className="p-5 text-sm text-texto-secundario">Todavía no hay propuestas. Sube tu primer export arriba.</p>
          )}
          {recientes.data?.map((cotizacion) => (
            <div key={cotizacion.id} className="flex flex-wrap items-center gap-x-6 gap-y-2 px-5 py-4">
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{cotizacion.nombre_cliente || 'Cliente sin nombre'}</p>
                <p className="text-sm text-texto-secundario">
                  {cotizacion.referencia_externa || 'Sin referencia'} · {fecha(cotizacion.creado_en)} · {cotizacion.total_items} ítems
                </p>
              </div>
              <div className="flex items-center gap-3">
                {cotizacion.items_pendientes > 0 && (
                  <span className="text-sm text-pendiente-texto">{cotizacion.items_pendientes} sin imagen</span>
                )}
                <PildoraEstadoCotizacion estado={cotizacion.estado} />
                <Link to={`/cotizaciones/${cotizacion.id}`}>
                  <Boton variante="secundario" icono={<ArrowRight className="h-4 w-4" />}>
                    Abrir
                  </Boton>
                </Link>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
