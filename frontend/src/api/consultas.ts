import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from './cliente'
import type { CotizacionDetalle } from './tipos'

// Las URLs firmadas duran 10 minutos: refrescamos antes de que caduquen.
const VIDA_URLS_MS = 4 * 60 * 1000

export const llaves = {
  cotizaciones: ['cotizaciones'] as const,
  cotizacion: (id: string) => ['cotizaciones', id] as const,
  imagenesDeItem: (itemId: string) => ['catalogo', itemId, 'imagenes'] as const,
  resumenBiblioteca: ['biblioteca', 'resumen'] as const,
}

export function useCotizaciones() {
  return useQuery({ queryKey: llaves.cotizaciones, queryFn: api.cotizaciones.listar })
}

export function useCotizacion(id: string | undefined) {
  return useQuery({
    queryKey: llaves.cotizacion(id ?? ''),
    queryFn: () => api.cotizaciones.obtener(id as string),
    enabled: Boolean(id),
    staleTime: VIDA_URLS_MS,
    refetchInterval: VIDA_URLS_MS,
  })
}

export function useCrearCotizacion() {
  const cliente = useQueryClient()
  return useMutation({
    mutationFn: api.cotizaciones.crear,
    onSuccess: (detalle) => {
      cliente.setQueryData(llaves.cotizacion(detalle.id), detalle)
      void cliente.invalidateQueries({ queryKey: llaves.cotizaciones })
    },
  })
}

export function useAsignarImagen(cotizacionId: string) {
  const cliente = useQueryClient()
  return useMutation({
    mutationFn: ({ itemId, imagenId }: { itemId: string; imagenId: string | null }) =>
      api.cotizaciones.asignarImagen(cotizacionId, itemId, imagenId),
    onSuccess: (detalle: CotizacionDetalle) => {
      cliente.setQueryData(llaves.cotizacion(cotizacionId), detalle)
      void cliente.invalidateQueries({ queryKey: llaves.cotizaciones })
      void cliente.invalidateQueries({ queryKey: llaves.resumenBiblioteca })
    },
  })
}

export function useGenerarPropuesta(cotizacionId: string) {
  const cliente = useQueryClient()
  return useMutation({
    mutationFn: () => api.cotizaciones.generar(cotizacionId),
    onSuccess: () => {
      void cliente.invalidateQueries({ queryKey: llaves.cotizacion(cotizacionId) })
      void cliente.invalidateQueries({ queryKey: llaves.cotizaciones })
    },
  })
}

export function useImagenesDeItem(itemId: string | null | undefined) {
  return useQuery({
    queryKey: llaves.imagenesDeItem(itemId ?? ''),
    queryFn: () => api.catalogo.imagenesDeItem(itemId as string),
    enabled: Boolean(itemId),
    staleTime: VIDA_URLS_MS,
  })
}

export function useSubirImagen() {
  const cliente = useQueryClient()
  return useMutation({
    mutationFn: api.imagenes.subir,
    onSuccess: (imagen) => {
      if (imagen.item_id) void cliente.invalidateQueries({ queryKey: llaves.imagenesDeItem(imagen.item_id) })
      void cliente.invalidateQueries({ queryKey: llaves.resumenBiblioteca })
    },
  })
}

export function useGenerarImagenes() {
  const cliente = useQueryClient()
  return useMutation({
    mutationFn: api.imagenes.generar,
    onSuccess: (_resultado, variables) => {
      void cliente.invalidateQueries({ queryKey: llaves.imagenesDeItem(variables.item_id) })
      void cliente.invalidateQueries({ queryKey: llaves.resumenBiblioteca })
    },
  })
}

export function useResumenBiblioteca() {
  return useQuery({ queryKey: llaves.resumenBiblioteca, queryFn: api.biblioteca.resumen })
}
