import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from './cliente'
import type { CatalogoItemActualizacion, CotizacionDetalle, UsuarioActualizacion } from './tipos'

// Las URLs firmadas duran 10 minutos: refrescamos antes de que caduquen.
const VIDA_URLS_MS = 4 * 60 * 1000

export const llaves = {
  perfil: ['perfil'] as const,
  cotizaciones: ['cotizaciones'] as const,
  cotizacion: (id: string) => ['cotizaciones', id] as const,
  catalogo: ['catalogo'] as const,
  itemsCatalogo: (buscar: string) => ['catalogo', 'items', buscar] as const,
  itemCatalogo: (id: string) => ['catalogo', 'item', id] as const,
  imagenesDeItem: (itemId: string) => ['catalogo', 'imagenes', itemId] as const,
  listasPrecios: ['catalogo', 'listas-precios'] as const,
  resumenBiblioteca: ['biblioteca', 'resumen'] as const,
  usuarios: ['usuarios'] as const,
}

// --- Salud ------------------------------------------------------------------

export function useSalud() {
  return useQuery({ queryKey: ['salud'], queryFn: api.salud, retry: 0, refetchInterval: 60 * 1000 })
}

// --- Perfil -----------------------------------------------------------------

export function usePerfil() {
  return useQuery({ queryKey: llaves.perfil, queryFn: api.perfil.yo, staleTime: 10 * 60 * 1000 })
}

// --- Cotizaciones -----------------------------------------------------------

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

// --- Catálogo ---------------------------------------------------------------

export function useCatalogo(buscar: string) {
  return useQuery({
    queryKey: llaves.itemsCatalogo(buscar),
    queryFn: () => api.catalogo.buscar(buscar),
    staleTime: VIDA_URLS_MS,
    placeholderData: (anterior) => anterior,
  })
}

export function useItemCatalogo(id: string | null | undefined) {
  return useQuery({
    queryKey: llaves.itemCatalogo(id ?? ''),
    queryFn: () => api.catalogo.obtener(id as string),
    enabled: Boolean(id),
    staleTime: VIDA_URLS_MS,
  })
}

export function useCrearItemCatalogo() {
  const cliente = useQueryClient()
  return useMutation({
    mutationFn: api.catalogo.crear,
    onSuccess: () => void cliente.invalidateQueries({ queryKey: llaves.catalogo }),
  })
}

export function useActualizarItemCatalogo() {
  const cliente = useQueryClient()
  return useMutation({
    mutationFn: ({ id, cambios }: { id: string; cambios: CatalogoItemActualizacion }) => api.catalogo.actualizar(id, cambios),
    onSuccess: (item) => {
      cliente.setQueryData(llaves.itemCatalogo(item.id), item)
      void cliente.invalidateQueries({ queryKey: llaves.catalogo })
    },
  })
}

export function useCargarTextoCatalogo() {
  const cliente = useQueryClient()
  return useMutation({
    mutationFn: api.catalogo.cargarTexto,
    onSuccess: () => {
      void cliente.invalidateQueries({ queryKey: llaves.catalogo })
      void cliente.invalidateQueries({ queryKey: llaves.resumenBiblioteca })
    },
  })
}

export function useListasPrecios() {
  return useQuery({ queryKey: llaves.listasPrecios, queryFn: api.catalogo.listasPrecios, staleTime: 10 * 60 * 1000 })
}

export function useCrearListaPrecios() {
  const cliente = useQueryClient()
  return useMutation({
    mutationFn: api.catalogo.crearListaPrecios,
    onSuccess: () => void cliente.invalidateQueries({ queryKey: llaves.catalogo }),
  })
}

export function useActualizarListaPrecios() {
  const cliente = useQueryClient()
  return useMutation({
    mutationFn: ({ id, cambios }: { id: string; cambios: { nombre?: string; orden?: number; activo?: boolean } }) =>
      api.catalogo.actualizarListaPrecios(id, cambios),
    onSuccess: () => void cliente.invalidateQueries({ queryKey: llaves.catalogo }),
  })
}

// --- Imágenes ---------------------------------------------------------------

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
      if (imagen.item_id) {
        void cliente.invalidateQueries({ queryKey: llaves.imagenesDeItem(imagen.item_id) })
        void cliente.invalidateQueries({ queryKey: llaves.itemCatalogo(imagen.item_id) })
      }
      void cliente.invalidateQueries({ queryKey: llaves.itemsCatalogo('') })
      void cliente.invalidateQueries({ queryKey: llaves.resumenBiblioteca })
    },
  })
}

export function useGenerarImagenes() {
  const cliente = useQueryClient()
  return useMutation({
    mutationFn: api.imagenes.generar,
    onSuccess: (resultado) => {
      const itemId = resultado.imagenes[0]?.item_id
      if (itemId) void cliente.invalidateQueries({ queryKey: llaves.imagenesDeItem(itemId) })
      void cliente.invalidateQueries({ queryKey: llaves.resumenBiblioteca })
    },
  })
}

// --- Biblioteca -------------------------------------------------------------

export function useResumenBiblioteca() {
  return useQuery({ queryKey: llaves.resumenBiblioteca, queryFn: api.biblioteca.resumen })
}

// --- Usuarios ---------------------------------------------------------------

export function useUsuarios(habilitado = true) {
  return useQuery({ queryKey: llaves.usuarios, queryFn: api.usuarios.listar, enabled: habilitado })
}

export function useCrearUsuario() {
  const cliente = useQueryClient()
  return useMutation({
    mutationFn: api.usuarios.crear,
    onSuccess: () => void cliente.invalidateQueries({ queryKey: llaves.usuarios }),
  })
}

export function useActualizarUsuario() {
  const cliente = useQueryClient()
  return useMutation({
    mutationFn: ({ id, cambios }: { id: string; cambios: UsuarioActualizacion }) => api.usuarios.actualizar(id, cambios),
    onSuccess: () => void cliente.invalidateQueries({ queryKey: llaves.usuarios }),
  })
}

export function useEliminarUsuario() {
  const cliente = useQueryClient()
  return useMutation({
    mutationFn: api.usuarios.eliminar,
    onSuccess: () => void cliente.invalidateQueries({ queryKey: llaves.usuarios }),
  })
}
