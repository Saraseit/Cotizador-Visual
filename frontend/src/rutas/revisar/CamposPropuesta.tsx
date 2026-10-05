import { useState } from 'react'
import { Link } from 'react-router-dom'

import { useGuardarCampos } from '@/api/consultas'
import type { CampoPropuesta } from '@/api/tipos'
import { Aviso, mensajeDeError } from '@/componentes/Aviso'
import { Boton } from '@/componentes/Boton'
import { Campo } from '@/componentes/Campo'
import { tipoDeInput } from '@/rutas/formato/FormatoPdf'

/** El predeterminado como se lee (las fechas, dd/mm/aaaa). */
const predeterminado = (campo: CampoPropuesta) =>
  campo.tipo === 'fecha' && /^\d{4}-\d{2}-\d{2}$/.test(campo.predeterminado)
    ? campo.predeterminado.split('-').reverse().join('/')
    : campo.predeterminado

/**
 * Datos extra del encabezado del PDF (fecha del evento, lugar…) para esta cotización. Los campos los
 * define un admin en "Formato del PDF"; vacío = se imprime el predeterminado (o nada).
 */
export function CamposPropuesta({
  cotizacionId,
  campos,
  valores,
}: {
  cotizacionId: string
  campos: CampoPropuesta[]
  valores: Record<string, string>
}) {
  const guardar = useGuardarCampos(cotizacionId)
  const [borrador, setBorrador] = useState<Record<string, string>>(valores)
  const cambios = campos.some((c) => (borrador[c.id] ?? '') !== (valores[c.id] ?? ''))

  return (
    <section className="tarjeta p-5" aria-labelledby="titulo-datos-propuesta">
      <h2 id="titulo-datos-propuesta" className="text-base font-semibold">
        Datos de la propuesta
      </h2>
      <p className="mt-1 text-sm text-texto-secundario">
        Salen en el encabezado del PDF. Vacío = el predeterminado.{' '}
        <Link to="/formato-pdf" className="underline">
          Formato del PDF
        </Link>
      </p>
      <div className="mt-4 flex flex-col gap-3">
        {campos.map((campo) => (
          <Campo key={campo.id} etiqueta={campo.etiqueta} ayuda={campo.predeterminado ? `Vacío = ${predeterminado(campo)}` : undefined}>
            <input
              type={tipoDeInput(campo.tipo)}
              value={borrador[campo.id] ?? ''}
              maxLength={200}
              placeholder={campo.predeterminado || undefined}
              onChange={(e) => setBorrador({ ...borrador, [campo.id]: e.target.value })}
            />
          </Campo>
        ))}
      </div>
      {guardar.isError && (
        <Aviso tono="error" className="mt-3">
          {mensajeDeError(guardar.error)}
        </Aviso>
      )}
      <div className="mt-4 flex justify-end">
        <Boton variante="secundario" disabled={!cambios} cargando={guardar.isPending} onClick={() => guardar.mutate(borrador)}>
          Guardar datos
        </Boton>
      </div>
    </section>
  )
}
