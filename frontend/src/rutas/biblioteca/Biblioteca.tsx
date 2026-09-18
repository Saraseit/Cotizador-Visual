import { Upload } from 'lucide-react'
import { useRef, useState } from 'react'

import { useResumenBiblioteca, useSubirImagen } from '@/api/consultas'
import type { ItemSinImagen } from '@/api/tipos'
import { Aviso, mensajeDeError } from '@/componentes/Aviso'
import { Boton } from '@/componentes/Boton'

function Metrica({ titulo, valor, detalle }: { titulo: string; valor: string; detalle?: string }) {
  return (
    <div className="tarjeta p-5">
      <p className="text-xs font-semibold uppercase tracking-wide text-texto-secundario">{titulo}</p>
      <p className="mt-2 font-titulo text-3xl">{valor}</p>
      {detalle && <p className="mt-1 text-sm text-texto-secundario">{detalle}</p>}
    </div>
  )
}

function FilaSinImagen({ item }: { item: ItemSinImagen }) {
  const entrada = useRef<HTMLInputElement>(null)
  const subir = useSubirImagen()
  const [listo, setListo] = useState(false)

  return (
    <tr>
      <td className="px-4 py-3 font-medium">{item.codigo}</td>
      <td className="px-4 py-3">{item.nombre}</td>
      <td className="px-4 py-3 text-texto-secundario">{item.categoria || '—'}</td>
      <td className="px-4 py-3 text-right tabular-nums">{item.veces_cotizado}</td>
      <td className="px-4 py-3 text-right">
        {listo ? (
          <span className="text-sm text-resuelto-texto">Imagen oficial subida</span>
        ) : (
          <>
            <Boton variante="secundario" icono={<Upload className="h-4 w-4" />} cargando={subir.isPending} onClick={() => entrada.current?.click()}>
              Subir
            </Boton>
            <input
              ref={entrada}
              type="file"
              accept="image/png,image/jpeg,image/webp"
              className="hidden"
              onChange={(evento) => {
                const archivo = evento.target.files?.[0]
                evento.target.value = ''
                if (!archivo) return
                subir.mutate({ archivo, itemId: item.id, tipo: 'oficial' }, { onSuccess: () => setListo(true) })
              }}
            />
          </>
        )}
        {subir.isError && <p className="mt-1 text-xs text-conceptual-texto">{mensajeDeError(subir.error)}</p>}
      </td>
    </tr>
  )
}

export function Biblioteca() {
  const resumen = useResumenBiblioteca()

  if (resumen.isLoading) return <p className="text-texto-secundario">Cargando biblioteca…</p>
  if (resumen.isError || !resumen.data) {
    return <Aviso tono="error">{resumen.error ? mensajeDeError(resumen.error) : 'No se pudo cargar el resumen.'}</Aviso>
  }
  const datos = resumen.data

  return (
    <div>
      <header>
        <h1 className="text-3xl">Biblioteca de imágenes</h1>
        <p className="mt-1 text-texto-secundario">
          Estado del catálogo compartido. Prioriza subir fotos oficiales de los ítems que más se cotizan.
        </p>
      </header>

      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Metrica
          titulo="Ítems activos con foto oficial"
          valor={`${datos.porcentaje_con_oficial}%`}
          detalle={`${datos.items_con_oficial} de ${datos.items_activos}`}
        />
        <Metrica titulo="Variantes" valor={String(datos.total_variantes)} detalle="Subidas por el equipo" />
        <Metrica titulo="Renders generados" valor={String(datos.total_generadas)} detalle="Imágenes conceptuales con IA" />
        <Metrica titulo="Sin ninguna imagen" valor={String(datos.total_sin_imagen)} detalle="Ítems activos del catálogo" />
      </div>

      <section className="mt-10">
        <h2 className="text-xl">Ítems más cotizados sin imagen</h2>
        <p className="mt-1 text-sm text-texto-secundario">
          Ordenados por las veces que aparecieron en una cotización. Al subir una foto queda como imagen oficial.
        </p>
        <div className="tarjeta mt-4 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-borde bg-fondo/60 text-left text-xs uppercase tracking-wide text-texto-secundario">
              <tr>
                <th className="px-4 py-3 font-semibold">Código</th>
                <th className="px-4 py-3 font-semibold">Nombre</th>
                <th className="px-4 py-3 font-semibold">Categoría</th>
                <th className="px-4 py-3 text-right font-semibold">Veces cotizado</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-borde">
              {datos.items_sin_imagen.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-10 text-center text-texto-secundario">
                    Todos los ítems activos tienen al menos una imagen.
                  </td>
                </tr>
              )}
              {datos.items_sin_imagen.map((item) => (
                <FilaSinImagen key={item.id} item={item} />
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
