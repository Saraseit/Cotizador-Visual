"""Cambios hechos en Revisar contra el sistema principal, e IVA.

La cotización nace del PDF del sistema, pero durante la negociación el vendedor puede agregar o quitar
partidas, cambiar cantidades y precios, y mover partidas de sección. Cada partida guarda lo que dice el
sistema (`*_sistema`); la diferencia es lo que falta aplicar allá. Cuando el vendedor marca que ya lo
aplicó, `alinear_cotizacion()` (SQL) hace que lo actual pase a ser lo del sistema.
"""

from __future__ import annotations

from app.db.modelos import Alineacion, CambioSistema, CotizacionItem, descripcion_impresa

TASA_IVA = 0.16  # se usa cuando el PDF del sistema no trae IVA ("más IVA")
TOLERANCIA = 0.005


def cantidad_sistema(item: CotizacionItem) -> float:
    return float(item.cantidad if item.cantidad_sistema is None else item.cantidad_sistema)


def precio_sistema(item: CotizacionItem) -> float:
    return float(item.precio_unitario if item.precio_sistema is None else item.precio_sistema)


def categoria_sistema(item: CotizacionItem) -> str:
    return item.categoria if item.categoria_sistema is None else item.categoria_sistema


def por_dias(item: CotizacionItem, dias: float) -> float:
    """Cuántas veces se cobra la partida: el mobiliario por día, flete y montaje una sola vez.

    Es la cuenta del sistema principal: SubTotal = mobiliario × DIAS + flete + montaje.
    """
    return 1 if item.cargo else dias


def base_sistema(todas: list[CotizacionItem], dias: float = 1) -> float:
    """Subtotal según el sistema principal (cargos incluidos): sus partidas con sus valores, también las
    que se quitaron en ProVista y sin las que se agregaron aquí, con el mobiliario por sus DIAS."""
    return round(
        sum(cantidad_sistema(i) * precio_sistema(i) * por_dias(i, dias) for i in todas if i.origen == "sistema"), 2
    )


def base_actual(items: list[CotizacionItem], dias: float = 1) -> float:
    """Lo mismo con lo que hay hoy en ProVista: partidas vigentes, el mobiliario por los días cobrados."""
    return round(sum(i.importe * por_dias(i, dias) for i in items if not i.eliminada), 2)


def tasa_iva(iva_documento: float | None, base_del_sistema: float) -> float:
    """La del PDF del sistema (IVA / subtotal) o, si no trae IVA, la general."""
    if iva_documento is not None and base_del_sistema > 0:
        return float(iva_documento) / base_del_sistema
    return TASA_IVA


def alineacion(todas: list[CotizacionItem], dias_cobrados: float = 1, dias_sistema: float = 1) -> Alineacion:
    """Qué cambió en ProVista respecto al sistema principal: los días cobrados y luego partida por partida."""
    cambios: list[CambioSistema] = []
    if abs(dias_cobrados - dias_sistema) >= TOLERANCIA:
        cambios.append(CambioSistema(tipo="dias", descripcion="Días cobrados", antes=dias_sistema, despues=dias_cobrados))
    for item in sorted(todas, key=lambda i: i.orden):
        comun = {"item_id": item.id, "codigo": item.codigo_origen, "descripcion": descripcion_impresa(item)}
        if item.eliminada:
            if item.origen == "sistema":
                cambios.append(CambioSistema(tipo="quitada", antes=round(cantidad_sistema(item) * precio_sistema(item), 2), **comun))
            continue
        if item.origen == "provista":
            cambios.append(CambioSistema(tipo="agregada", despues=item.importe, **comun))
            continue
        if abs(float(item.cantidad) - cantidad_sistema(item)) >= TOLERANCIA:
            cambios.append(CambioSistema(tipo="cantidad", antes=cantidad_sistema(item), despues=float(item.cantidad), **comun))
        if abs(float(item.precio_unitario) - precio_sistema(item)) >= TOLERANCIA:
            cambios.append(CambioSistema(tipo="precio", antes=precio_sistema(item), despues=float(item.precio_unitario), **comun))
        if (item.categoria or "") != (categoria_sistema(item) or ""):
            cambios.append(CambioSistema(tipo="seccion", antes=categoria_sistema(item), despues=item.categoria, **comun))
    diferencia = base_actual(todas, dias_cobrados) - base_sistema(todas, dias_sistema)
    return Alineacion(alineada=not cambios, cambios=cambios, diferencia_importe=round(diferencia, 2))


def esta_alineada(filas: list[dict], dias_cobrados: float = 1, dias_sistema: float = 1) -> bool:
    """Versión barata para la lista de Propuestas (filas crudas de `cotizacion_items`)."""
    if abs(dias_cobrados - dias_sistema) >= TOLERANCIA:
        return False
    for fila in filas:
        if fila.get("origen") == "provista" or fila.get("eliminada"):
            return False
        for actual, sistema in (("cantidad", "cantidad_sistema"), ("precio_unitario", "precio_sistema")):
            if fila.get(sistema) is not None and abs(float(fila.get(actual) or 0) - float(fila[sistema])) >= TOLERANCIA:
                return False
        if fila.get("categoria_sistema") is not None and (fila.get("categoria") or "") != fila["categoria_sistema"]:
            return False
    return True
