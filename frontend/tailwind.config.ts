import type { Config } from 'tailwindcss'

// Tokens de diseño de ProVista. Todo el color y la tipografía sale de aquí.
// Los colores son variables CSS (canales RGB, ver src/index.css) para que existan dos paletas,
// clara y oscura, y para que los modificadores de opacidad (bg-fondo/60) sigan funcionando.
const color = (variable: string) => `rgb(var(--${variable}) / <alpha-value>)`

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        fondo: color('fondo'),
        superficie: color('superficie'),
        // Fondo del velo que cubre la página detrás de una ventana emergente.
        velo: color('velo'),
        texto: {
          DEFAULT: color('texto'),
          secundario: color('texto-secundario'),
        },
        borde: color('borde'),
        acento: {
          DEFAULT: color('acento'),
          oscuro: color('acento-oscuro'),
          suave: color('acento-suave'),
        },
        pendiente: {
          fondo: color('pendiente-fondo'),
          texto: color('pendiente-texto'),
          borde: color('pendiente-borde'),
        },
        resuelto: {
          fondo: color('resuelto-fondo'),
          texto: color('resuelto-texto'),
        },
        conceptual: {
          fondo: color('conceptual-fondo'),
          texto: color('conceptual-texto'),
        },
      },
      fontFamily: {
        titulo: ['Fraunces', 'Georgia', 'serif'],
        cuerpo: ['"IBM Plex Sans"', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        boton: '10px',
        tarjeta: '12px',
        pildora: '999px',
      },
      minHeight: {
        boton: '44px',
      },
    },
  },
  plugins: [],
} satisfies Config
