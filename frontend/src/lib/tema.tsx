import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

/** Preferencia del usuario: seguir al sistema operativo o fijar claro/oscuro. */
export type PreferenciaTema = 'sistema' | 'claro' | 'oscuro'

const LLAVE = 'provista-tema'
const CONSULTA_OSCURO = '(prefers-color-scheme: dark)'

interface EstadoTema {
  preferencia: PreferenciaTema
  /** Tema que se está mostrando realmente. */
  efectivo: 'claro' | 'oscuro'
  /** Alterna sistema → claro → oscuro → sistema. */
  ciclar: () => void
}

const ContextoTema = createContext<EstadoTema | null>(null)

function leerPreferencia(): PreferenciaTema {
  try {
    const valor = localStorage.getItem(LLAVE)
    if (valor === 'claro' || valor === 'oscuro' || valor === 'sistema') return valor
  } catch {
    // almacenamiento no disponible (modo privado, bloqueado): se sigue al sistema
  }
  return 'sistema'
}

function sistemaEsOscuro(): boolean {
  return typeof window !== 'undefined' && window.matchMedia(CONSULTA_OSCURO).matches
}

const SIGUIENTE: Record<PreferenciaTema, PreferenciaTema> = { sistema: 'claro', claro: 'oscuro', oscuro: 'sistema' }

export function ProveedorTema({ children }: { children: ReactNode }) {
  const [preferencia, setPreferencia] = useState<PreferenciaTema>(leerPreferencia)
  const [sistemaOscuro, setSistemaOscuro] = useState<boolean>(sistemaEsOscuro)

  // Mientras se sigue al sistema, reaccionar a que cambie (por ejemplo al anochecer).
  useEffect(() => {
    const consulta = window.matchMedia(CONSULTA_OSCURO)
    const alCambiar = (evento: MediaQueryListEvent) => setSistemaOscuro(evento.matches)
    consulta.addEventListener('change', alCambiar)
    return () => consulta.removeEventListener('change', alCambiar)
  }, [])

  const efectivo: 'claro' | 'oscuro' = preferencia === 'sistema' ? (sistemaOscuro ? 'oscuro' : 'claro') : preferencia

  useEffect(() => {
    document.documentElement.classList.toggle('dark', efectivo === 'oscuro')
  }, [efectivo])

  const valor = useMemo<EstadoTema>(
    () => ({
      preferencia,
      efectivo,
      ciclar: () => {
        const siguiente = SIGUIENTE[preferencia]
        setPreferencia(siguiente)
        try {
          localStorage.setItem(LLAVE, siguiente)
        } catch {
          // sin almacenamiento: el cambio vale sólo para esta sesión
        }
      },
    }),
    [preferencia, efectivo],
  )

  return <ContextoTema.Provider value={valor}>{children}</ContextoTema.Provider>
}

export function useTema(): EstadoTema {
  const contexto = useContext(ContextoTema)
  if (!contexto) throw new Error('useTema debe usarse dentro de ProveedorTema')
  return contexto
}
