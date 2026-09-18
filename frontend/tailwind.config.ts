import type { Config } from 'tailwindcss'

// Tokens de diseño del Cotizador visual. Todo el color y la tipografía sale de aquí.
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        fondo: '#F2F0EB',
        superficie: '#FFFFFF',
        texto: {
          DEFAULT: '#1A1916',
          secundario: '#57534A',
        },
        borde: '#DDD8CE',
        acento: {
          DEFAULT: '#8C4A2F',
          oscuro: '#6F3A24',
          suave: '#F3E5DE',
        },
        pendiente: {
          fondo: '#FDF8EC',
          texto: '#6B4E0A',
          borde: '#E3CE94',
        },
        resuelto: {
          fondo: '#E7F0EA',
          texto: '#235741',
        },
        conceptual: {
          fondo: '#F3E5DE',
          texto: '#7A3D22',
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
