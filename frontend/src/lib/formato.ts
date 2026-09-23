const formatoMoneda = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' })
const formatoFecha = new Intl.DateTimeFormat('es-MX', { dateStyle: 'medium' })
const formatoFechaHora = new Intl.DateTimeFormat('es-MX', { dateStyle: 'medium', timeStyle: 'short' })
const formatoCantidad = new Intl.NumberFormat('es-MX', { maximumFractionDigits: 2 })

const formatoDolares = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })

export const moneda = (valor: number) => formatoMoneda.format(valor)

/**
 * Formatea como lo hará el PDF: en dólares divide entre el tipo de cambio que puso el vendedor.
 * Sin tipo de cambio no se inventa la conversión y se queda en pesos.
 */
export function formatoDinero(moneda: 'MXN' | 'USD', tipoCambio: number | null) {
  if (moneda === 'USD' && tipoCambio) return (valor: number) => `US${formatoDolares.format(valor / tipoCambio)}`
  return (valor: number) => formatoMoneda.format(valor)
}
export const fecha = (iso: string) => formatoFecha.format(new Date(iso))
export const fechaHora = (iso: string) => formatoFechaHora.format(new Date(iso))
export const cantidad = (valor: number) => formatoCantidad.format(valor)
