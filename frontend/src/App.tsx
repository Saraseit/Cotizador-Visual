import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { Disposicion } from '@/componentes/Disposicion'
import { ProveedorSesion, RutaProtegida } from '@/lib/sesion'
import { ProveedorTema } from '@/lib/tema'
import { Biblioteca } from '@/rutas/biblioteca/Biblioteca'
import { Catalogo } from '@/rutas/catalogo/Catalogo'
import { Entrar } from '@/rutas/entrar/Entrar'
import { Estado } from '@/rutas/estado/Estado'
import { Generar } from '@/rutas/generar/Generar'
import { Presentacion } from '@/rutas/presentacion/Presentacion'
import { Revisar } from '@/rutas/revisar/Revisar'
import { Subir } from '@/rutas/subir/Subir'
import { Usuarios } from '@/rutas/usuarios/Usuarios'

const clienteConsultas = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
})

export function App() {
  return (
    <QueryClientProvider client={clienteConsultas}>
      <ProveedorTema>
      <ProveedorSesion>
        <BrowserRouter>
          <Routes>
            <Route path="/entrar" element={<Entrar />} />
            <Route
              element={
                <RutaProtegida>
                  <Disposicion />
                </RutaProtegida>
              }
            >
              <Route path="/" element={<Subir />} />
              <Route path="/cotizaciones/:id" element={<Revisar />} />
              <Route path="/cotizaciones/:id/generar" element={<Generar />} />
              <Route path="/cotizaciones/:id/presentacion" element={<Presentacion />} />
              <Route path="/catalogo" element={<Catalogo />} />
              <Route path="/biblioteca" element={<Biblioteca />} />
              <Route path="/usuarios" element={<Usuarios />} />
              <Route path="/estado" element={<Estado />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </ProveedorSesion>
      </ProveedorTema>
    </QueryClientProvider>
  )
}
