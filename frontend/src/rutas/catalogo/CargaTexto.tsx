import { ClipboardPaste } from 'lucide-react'
import { useState } from 'react'

import { useCargarTextoCatalogo } from '@/api/consultas'
import { Aviso, mensajeDeError } from '@/componentes/Aviso'
import { Boton } from '@/componentes/Boton'
import { Modal } from '@/componentes/Modal'

const EJEMPLO = `codigo; nombre; categoria; descripcion; medidas; costo de reposicion; etiquetas
SIL-020; Silla Luis XV dorada; Sillas; Silla clásica tapizada en lino; 45 x 50 x 95 cm; 1250; boda|clásico
MES-020; Mesa rústica 2.4 m; Mesas; ; 240 x 100 x 76 cm; 4800; exterior`

export function CargaTexto({ alCerrar }: { alCerrar: () => void }) {
  const [texto, setTexto] = useState('')
  const cargar = useCargarTextoCatalogo()

  return (
    <Modal abierto titulo="Carga por texto" subtitulo="Pega una línea por ítem. Sólo el código es obligatorio." alCerrar={alCerrar}>
      <div className="flex flex-col gap-4">
        <Aviso tono="info">
          Orden de columnas: <strong>código; nombre; categoría; descripción; medidas; costo de reposición; etiquetas</strong>.
          Separa con punto y coma, tabulador (pegado desde Excel) o coma. Las etiquetas van separadas por barra vertical. Si
          el código ya existe, el ítem se actualiza.
        </Aviso>

        <textarea
          rows={10}
          value={texto}
          onChange={(evento) => setTexto(evento.target.value)}
          placeholder={EJEMPLO}
          className="font-mono text-xs"
          spellCheck={false}
        />

        {cargar.isError && <Aviso tono="error">{mensajeDeError(cargar.error)}</Aviso>}
        {cargar.data && (
          <div className="flex flex-col gap-2">
            <Aviso tono={cargar.data.creados + cargar.data.actualizados > 0 ? 'info' : 'ambar'}>
              {cargar.data.creados} creados · {cargar.data.actualizados} actualizados
              {cargar.data.errores.length > 0 && ` · ${cargar.data.errores.length} líneas con avisos`}
            </Aviso>
            {cargar.data.errores.length > 0 && (
              <ul className="list-disc pl-6 text-sm text-conceptual-texto">
                {cargar.data.errores.map((error) => (
                  <li key={error}>{error}</li>
                ))}
              </ul>
            )}
            {cargar.data.items.length > 0 && (
              <p className="text-sm text-texto-secundario">
                Ítems: {cargar.data.items.map((i) => i.codigo).join(', ')}. Después edita cada uno para subir su foto y poner
                precios.
              </p>
            )}
          </div>
        )}

        <div className="flex justify-end gap-2">
          <Boton variante="secundario" onClick={alCerrar}>
            Cerrar
          </Boton>
          <Boton
            icono={<ClipboardPaste className="h-4 w-4" />}
            cargando={cargar.isPending}
            disabled={!texto.trim()}
            onClick={() => cargar.mutate(texto, { onSuccess: (resultado) => resultado.errores.length === 0 && setTexto('') })}
          >
            Cargar ítems
          </Boton>
        </div>
      </div>
    </Modal>
  )
}
