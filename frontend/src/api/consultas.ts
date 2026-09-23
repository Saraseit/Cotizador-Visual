import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from './cliente'
import type {
  Cargo,
  CatalogoItemActualizacion,
  ConfigPresentacionEntrada,
  CotizacionDetalle,
  PaletaEntrada,
  ParametrosPlantilla,
  Presentacion,
  UsuarioActualizacion,
} from './tipos'

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
  pdfsCotizacion: (id: string) => ['cotizaciones', id, 'pdfs'] as const,
  presentacion: (id: string) => ['cotizaciones', id, 'presentacion'] as const,
  ambientacion: ['imagenes', 'ambientacion'] as const,
  plantillas: ['plantillas'] as const,
  paletas: ['paletas'] as const,
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

/** PDF generados de una cotización (propuesta base y presentación editorial), para la pantalla Propuestas. */
export function usePdfsCotizacion(cotizacionId: string, habilitado = true) {
  return useQuery({
    queryKey: llaves.pdfsCotizacion(cotizacionId),
    queryFn: () => api.cotizaciones.pdfs(cotizacionId),
    enabled: Boolean(cotizacionId) && habilitado,
    staleTime: VIDA_URLS_MS,
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

/**
 * Las ediciones de una misma cotización (imagen, orden, tipo) pueden ir en paralelo y sus respuestas
 * llegar desordenadas: una respuesta vieja pisaría un cambio más nuevo. Por eso sólo la última edición
 * pendiente aplica su respuesta, y además se vuelve a leer la cotización para quedar con lo guardado.
 */
const llaveEdicion = (cotizacionId: string) => ['cotizaciones', cotizacionId, 'edicion'] as const

function useAlTerminarEdicion(cotizacionId: string) {
  const cliente = useQueryClient()
  return (detalle: CotizacionDetalle | undefined) => {
    if (cliente.isMutating({ mutationKey: llaveEdicion(cotizacionId) }) > 1) return
    if (detalle) cliente.setQueryData(llaves.cotizacion(cotizacionId), detalle)
    void cliente.invalidateQueries({ queryKey: llaves.cotizacion(cotizacionId), exact: true })
  }
}

export function useAsignarImagen(cotizacionId: string) {
  const cliente = useQueryClient()
  const alTerminar = useAlTerminarEdicion(cotizacionId)
  return useMutation({
    mutationKey: llaveEdicion(cotizacionId),
    mutationFn: ({ itemId, imagenId }: { itemId: string; imagenId: string | null }) =>
      api.cotizaciones.asignarImagen(cotizacionId, itemId, imagenId),
    onSettled: (detalle) => alTerminar(detalle),
    onSuccess: () => {
      void cliente.invalidateQueries({ queryKey: llaves.cotizaciones, exact: true })
      void cliente.invalidateQueries({ queryKey: llaves.resumenBiblioteca })
    },
  })
}

/** Guarda el orden de impresión. Actualiza la pantalla al instante y revierte si el servidor falla. */
export function useReordenar(cotizacionId: string) {
  const cliente = useQueryClient()
  const llave = llaves.cotizacion(cotizacionId)
  const alTerminar = useAlTerminarEdicion(cotizacionId)
  return useMutation({
    mutationKey: llaveEdicion(cotizacionId),
    mutationFn: (ids: string[]) => api.cotizaciones.reordenar(cotizacionId, ids),
    onMutate: async (ids: string[]) => {
      await cliente.cancelQueries({ queryKey: llave })
      const anterior = cliente.getQueryData<CotizacionDetalle>(llave)
      if (anterior) {
        const posicion = new Map(ids.map((id, indice) => [id, indice]))
        const items = anterior.items.map((i) => ({ ...i, orden: posicion.get(i.id) ?? ids.length + i.orden }))
        cliente.setQueryData<CotizacionDetalle>(llave, { ...anterior, items: items.sort((a, b) => a.orden - b.orden) })
      }
      return { anterior }
    },
    onError: (_error, _ids, contexto) => {
      if (contexto?.anterior) cliente.setQueryData(llave, contexto.anterior)
    },
    onSettled: (detalle) => alTerminar(detalle),
  })
}

export function useAsignarCargo(cotizacionId: string) {
  const cliente = useQueryClient()
  const alTerminar = useAlTerminarEdicion(cotizacionId)
  return useMutation({
    mutationKey: llaveEdicion(cotizacionId),
    mutationFn: ({ itemId, cargo }: { itemId: string; cargo: Cargo | null }) => api.cotizaciones.asignarCargo(cotizacionId, itemId, cargo),
    onSettled: (detalle) => alTerminar(detalle),
    onSuccess: () => void cliente.invalidateQueries({ queryKey: llaves.cotizaciones, exact: true }),
  })
}

export function useGenerarPropuesta(cotizacionId: string) {
  const cliente = useQueryClient()
  return useMutation({
    mutationFn: () => api.cotizaciones.generar(cotizacionId),
    onSuccess: () => {
      void cliente.invalidateQueries({ queryKey: llaves.cotizacion(cotizacionId) })
      void cliente.invalidateQueries({ queryKey: llaves.cotizaciones })
      void cliente.invalidateQueries({ queryKey: llaves.pdfsCotizacion(cotizacionId) })
    },
  })
}

// --- Presentación editorial -------------------------------------------------

export function usePresentacion(cotizacionId: string | undefined) {
  return useQuery({
    queryKey: llaves.presentacion(cotizacionId ?? ''),
    queryFn: () => api.presentacion.obtener(cotizacionId as string),
    enabled: Boolean(cotizacionId),
    staleTime: VIDA_URLS_MS,
    refetchInterval: VIDA_URLS_MS,
  })
}

/** Todas las respuestas del editor traen la presentación completa: se guarda tal cual en caché. */
function useMutacionPresentacion<T>(cotizacionId: string, fn: (valor: T) => Promise<Presentacion>) {
  const cliente = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: (presentacion: Presentacion) => cliente.setQueryData(llaves.presentacion(cotizacionId), presentacion),
  })
}

export function useGuardarPresentacion(cotizacionId: string) {
  return useMutacionPresentacion(cotizacionId, (config: ConfigPresentacionEntrada) => api.presentacion.guardar(cotizacionId, config))
}

export function useAsignarImagenPresentacion(cotizacionId: string) {
  return useMutacionPresentacion(cotizacionId, ({ hueco, imagenId }: { hueco: string; imagenId: string | null }) =>
    api.presentacion.asignarImagen(cotizacionId, hueco, imagenId),
  )
}

export function useGenerarMontaje(cotizacionId: string) {
  const cliente = useQueryClient()
  return useMutation({
    mutationFn: ({ clave, indicaciones }: { clave: string; indicaciones?: string }) =>
      api.presentacion.generarMontaje(cotizacionId, clave, indicaciones ?? ''),
    onSuccess: (presentacion: Presentacion) => {
      cliente.setQueryData(llaves.presentacion(cotizacionId), presentacion)
      void cliente.invalidateQueries({ queryKey: llaves.resumenBiblioteca })
    },
  })
}

export function useTraducirPresentacion(cotizacionId: string) {
  return useMutacionPresentacion(cotizacionId, () => api.presentacion.traducir(cotizacionId))
}

/** Nota de la partida para esta cotización. No toca el catálogo ni el sistema de la empresa. */
export function useEditarDescripcion(cotizacionId: string) {
  const cliente = useQueryClient()
  return useMutation({
    mutationFn: ({ itemId, descripcion }: { itemId: string; descripcion: string }) =>
      api.cotizaciones.editarDescripcion(cotizacionId, itemId, descripcion),
    onSuccess: (detalle: CotizacionDetalle) => cliente.setQueryData(llaves.cotizacion(cotizacionId), detalle),
  })
}

// --- Plantillas y paletas ---------------------------------------------------

export function usePlantillas(habilitado = true) {
  return useQuery({
    queryKey: llaves.plantillas,
    queryFn: api.plantillas.listar,
    enabled: habilitado,
    staleTime: VIDA_URLS_MS,
  })
}

function useMutacionPlantillas<T>(fn: (valor: T) => Promise<unknown>) {
  const cliente = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: () => void cliente.invalidateQueries({ queryKey: llaves.plantillas }),
  })
}

export function useCrearPlantilla() {
  return useMutacionPlantillas(({ archivo, nombre }: { archivo: File; nombre?: string }) => api.plantillas.crear(archivo, nombre ?? ''))
}

export function useActualizarPlantilla() {
  return useMutacionPlantillas(
    ({ id, cambios }: { id: string; cambios: { nombre?: string; descripcion?: string; parametros?: ParametrosPlantilla } }) =>
      api.plantillas.actualizar(id, cambios),
  )
}

export function useAgregarInspiracion() {
  return useMutacionPlantillas(({ id, archivo }: { id: string; archivo: File }) => api.plantillas.agregarInspiracion(id, archivo))
}

export function useQuitarInspiracion() {
  return useMutacionPlantillas(({ id, imagenId }: { id: string; imagenId: string }) => api.plantillas.quitarInspiracion(id, imagenId))
}

export function useAnalizarPlantilla() {
  return useMutacionPlantillas((id: string) => api.plantillas.analizar(id))
}

export function useEliminarPlantilla() {
  return useMutacionPlantillas((id: string) => api.plantillas.eliminar(id))
}

export function usePaletas(habilitado = true) {
  return useQuery({ queryKey: llaves.paletas, queryFn: api.paletas.listar, enabled: habilitado, staleTime: 10 * 60 * 1000 })
}

function useMutacionPaletas<T>(fn: (valor: T) => Promise<unknown>) {
  const cliente = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: () => void cliente.invalidateQueries({ queryKey: llaves.paletas }),
  })
}

export function useGuardarPaleta() {
  return useMutacionPaletas(({ id, entrada }: { id?: string | null; entrada: PaletaEntrada }) =>
    id ? api.paletas.actualizar(id, entrada) : api.paletas.crear(entrada),
  )
}

export function useEliminarPaleta() {
  return useMutacionPaletas((id: string) => api.paletas.eliminar(id))
}

export function useGenerarPdfPresentacion(cotizacionId: string) {
  const cliente = useQueryClient()
  return useMutation({
    mutationFn: () => api.presentacion.pdf(cotizacionId),
    onSuccess: () => {
      void cliente.invalidateQueries({ queryKey: llaves.cotizaciones, exact: true })
      void cliente.invalidateQueries({ queryKey: llaves.pdfsCotizacion(cotizacionId) })
    },
  })
}

export function useAmbientacion(habilitado = true) {
  return useQuery({
    queryKey: llaves.ambientacion,
    queryFn: api.imagenes.ambientacion,
    enabled: habilitado,
    staleTime: VIDA_URLS_MS,
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
      if (imagen.tipo === 'ambientacion') void cliente.invalidateQueries({ queryKey: llaves.ambientacion })
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
