const formatoMoneda = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' })
const formatoFecha = new Intl.DateTimeFormat('es-MX', { dateStyle: 'medium' })
const formatoCantidad = new Intl.NumberFormat('es-MX', { maximumFractionDigits: 2 })

export const moneda = (valor: number) => formatoMoneda.format(valor)
export const fecha = (iso: string) => formatoFecha.format(new Date(iso))
export const cantidad = (valor: number) => formatoCantidad.format(valor)
