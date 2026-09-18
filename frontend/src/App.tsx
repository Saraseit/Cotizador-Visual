import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { Disposicion } from '@/componentes/Disposicion'
import { ProveedorSesion, RutaProtegida } from '@/lib/sesion'
import { Biblioteca } from '@/rutas/biblioteca/Biblioteca'
import { Entrar } from '@/rutas/entrar/Entrar'
import { Generar } from '@/rutas/generar/Generar'
import { Revisar } from '@/rutas/revisar/Revisar'
import { Subir } from '@/rutas/subir/Subir'

const clienteConsultas = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
})

export function App() {
  return (
    <QueryClientProvider client={clienteConsultas}>
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
              <Route path="/biblioteca" element={<Biblioteca />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </ProveedorSesion>
    </QueryClientProvider>
  )
}
