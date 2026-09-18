import { UploadCloud } from 'lucide-react'
import { useRef, useState, type DragEvent } from 'react'

interface Props {
  alSeleccionar: (archivo: File) => void
  aceptar?: string
  ocupado?: boolean
  titulo?: string
  descripcion?: string
}

export function ZonaArrastre({
  alSeleccionar,
  aceptar = '.xlsx,.pdf',
  ocupado = false,
  titulo = 'Arrastra aquí el export del sistema',
  descripcion = 'o haz clic para elegir el archivo (.xlsx o .pdf)',
}: Props) {
  const entrada = useRef<HTMLInputElement>(null)
  const [arrastrando, setArrastrando] = useState(false)

  const recibir = (archivos: FileList | null) => {
    const archivo = archivos?.[0]
    if (archivo) alSeleccionar(archivo)
  }

  const alSoltar = (evento: DragEvent<HTMLDivElement>) => {
    evento.preventDefault()
    setArrastrando(false)
    if (!ocupado) recibir(evento.dataTransfer.files)
  }

  return (
    <div
      role="button"
      tabIndex={0}
      aria-busy={ocupado}
      onClick={() => !ocupado && entrada.current?.click()}
      onKeyDown={(evento) => {
        if (evento.key === 'Enter' || evento.key === ' ') entrada.current?.click()
      }}
      onDragOver={(evento) => {
        evento.preventDefault()
        setArrastrando(true)
      }}
      onDragLeave={() => setArrastrando(false)}
      onDrop={alSoltar}
      className={`flex min-h-[260px] cursor-pointer flex-col items-center justify-center gap-3 rounded-tarjeta border-2 border-dashed px-6 text-center transition-colors ${
        arrastrando ? 'border-acento bg-acento-suave/40' : 'border-borde bg-superficie hover:border-texto-secundario'
      } ${ocupado ? 'cursor-wait opacity-70' : ''}`}
    >
      <span className="flex h-14 w-14 items-center justify-center rounded-full bg-fondo text-acento">
        <UploadCloud className="h-7 w-7" aria-hidden />
      </span>
      <div>
        <p className="text-lg font-medium">{ocupado ? 'Procesando el archivo…' : titulo}</p>
        <p className="mt-1 text-sm text-texto-secundario">{descripcion}</p>
      </div>
      <input
        ref={entrada}
        type="file"
        accept={aceptar}
        className="hidden"
        onChange={(evento) => {
          recibir(evento.target.files)
          evento.target.value = ''
        }}
      />
    </div>
  )
}
