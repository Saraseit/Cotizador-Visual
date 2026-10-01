"""Artículos compuestos: varias partidas que se presentan como un solo artículo.

El vendedor los arma en Revisar (p. ej. la cubierta y la base de una mesa). En los PDF el compuesto
ocupa un renglón con su foto y su nombre, y debajo van sus partidas.

Precio del compuesto (`precio_modo`):
  - 'suma': la suma de sus partidas. Subtotal y total quedan igual que en el PDF del sistema.
  - 'partida': se queda el precio unitario de una de sus partidas (p. ej. la cubierta ya incluye la base).
  - 'manual': un precio unitario que escribe el vendedor.
Con 'partida' o 'manual' la propuesta deja de cuadrar con el PDF del sistema; `cuadre()` lo calcula
para que Revisar lo avise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from app.db.modelos import AjustePrecio, Compuesto, CotizacionItem, Cuadre, descripcion_impresa

LARGO_NOMBRE = 200


@dataclass
class Renglon:
    """Lo que se imprime como una unidad: una partida suelta o un compuesto con sus partidas."""

    items: list[CotizacionItem] = field(default_factory=list)
    compuesto: Compuesto | None = None

    @property
    def primero(self) -> CotizacionItem:
        return self.items[0]

    @property
    def categoria(self) -> str:
        return self.primero.categoria

    @property
    def cantidad_comun(self) -> float | None:
        """Cantidad del artículo si todas sus partidas traen la misma (10 cubiertas + 10 bases = 10 mesas)."""
        cantidades = {float(i.cantidad) for i in self.items}
        return cantidades.pop() if len(cantidades) == 1 else None

    @property
    def partida_precio(self) -> CotizacionItem | None:
        """La partida cuyo precio se queda (modo 'partida'); None si no aplica o ya no está en el compuesto."""
        if not self.compuesto or self.compuesto.precio_modo != "partida":
            return None
        return next((i for i in self.items if i.id == self.compuesto.precio_item_id), None)

    @property
    def modo(self) -> str:
        """Modo de precio efectivo: si falta el dato del modo elegido, vuelve a 'suma'."""
        if not self.compuesto:
            return "suma"
        if self.compuesto.precio_modo == "partida" and self.partida_precio:
            return "partida"
        if self.compuesto.precio_modo == "manual" and self.compuesto.precio_manual is not None:
            return "manual"
        return "suma"

    @property
    def cantidad(self) -> float | None:
        """Cuántos artículos completos se presentan. None = partidas con cantidades distintas (sólo en 'suma')."""
        if self.modo == "partida":
            return float(self.partida_precio.cantidad)  # type: ignore[union-attr]
        if self.modo == "manual":
            return self.cantidad_comun if self.cantidad_comun is not None else float(self.primero.cantidad)
        return self.cantidad_comun

    @property
    def precio_unitario(self) -> float | None:
        """Precio de un artículo completo. En 'suma' es la suma de los unitarios (sólo con cantidad común)."""
        if self.modo == "partida":
            return round(float(self.partida_precio.precio_unitario), 2)  # type: ignore[union-attr]
        if self.modo == "manual":
            return round(float(self.compuesto.precio_manual), 2)  # type: ignore[union-attr, arg-type]
        if self.cantidad_comun is None:
            return None
        return round(sum(float(i.precio_unitario) for i in self.items), 2)

    @property
    def importe_partidas(self) -> float:
        """Lo que suman sus partidas en el PDF del sistema."""
        return round(sum(i.importe for i in self.items), 2)

    @property
    def importe(self) -> float:
        """Importe que se presenta. Distinto de `importe_partidas` si se cambió el precio."""
        if self.modo == "suma":
            return self.importe_partidas
        return round((self.cantidad or 0) * (self.precio_unitario or 0), 2)

    @property
    def precio_cambiado(self) -> bool:
        return abs(self.importe - self.importe_partidas) >= 0.005

    @property
    def imagen_id(self) -> UUID | None:
        return self.compuesto.imagen_id if self.compuesto else self.primero.imagen_id

    @property
    def es_render_conceptual(self) -> bool:
        if self.compuesto:
            return bool(self.compuesto.imagen and self.compuesto.imagen.tipo == "generada")
        return self.primero.es_render_conceptual


def renglones(partidas: list[CotizacionItem], compuestos: list[Compuesto]) -> list[Renglon]:
    """Agrupa las partidas (ya ordenadas y sin cargos) en renglones.

    El compuesto ocupa el lugar de su primera partida; las demás se le suman aunque estén más abajo.
    """
    por_id = {c.id: c for c in compuestos}
    abiertos: dict[UUID, Renglon] = {}
    resultado: list[Renglon] = []
    for item in partidas:
        compuesto = por_id.get(item.compuesto_id) if item.compuesto_id else None
        if compuesto is None:
            resultado.append(Renglon([item]))
        elif compuesto.id in abiertos:
            abiertos[compuesto.id].items.append(item)
        else:
            abiertos[compuesto.id] = Renglon([item], compuesto)
            resultado.append(abiertos[compuesto.id])
    return resultado


def categoria_efectiva(items: list[CotizacionItem], compuestos: list[Compuesto]) -> dict[UUID, str]:
    """Sección en la que se imprime cada partida: la suya o, si es parte de un compuesto, la de la
    primera partida del compuesto (para que el artículo no quede partido entre dos secciones)."""
    ids = {c.id for c in compuestos}
    primera: dict[UUID, str] = {}
    resultado: dict[UUID, str] = {}
    for item in sorted(items, key=lambda i: i.orden):
        if item.compuesto_id in ids:
            resultado[item.id] = primera.setdefault(item.compuesto_id, item.categoria)  # type: ignore[arg-type]
        else:
            resultado[item.id] = item.categoria
    return resultado


def nombre_por_defecto(items: list[CotizacionItem]) -> str:
    """'CUBIERTA REDONDA 1.80 + BASE DE HIERRO NEGRA': las descripciones de las partidas, unidas."""
    nombre = " + ".join(descripcion_impresa(i).strip() for i in items if descripcion_impresa(i).strip())
    return nombre[:LARGO_NOMBRE].strip() or "ARTÍCULO COMPUESTO"


def prompt_compuesto(items: list[CotizacionItem], nombre: str, peticion: str = "") -> str:
    """Petición para la IA: armar el artículo completo a partir de las fotos de sus piezas."""
    piezas = "\n".join(f"- {descripcion_impresa(i).strip()}" for i in items)
    partes = [
        f'Un solo artículo de mobiliario para eventos, completo y armado: "{nombre.strip()}". '
        "Se forma con estas piezas, que se rentan por separado:\n" + piezas,
        (
            "Cada imagen adjunta es la foto de una de esas piezas por separado. Combínalas en el artículo "
            "completo, montado como se usa (por ejemplo, la cubierta sobre la base), respetando la forma, el "
            "material, el color y las proporciones de cada pieza. Una sola unidad del artículo."
        ),
    ]
    if peticion.strip():
        partes.append(f"Indicaciones del vendedor: {peticion.strip()}")
    return "\n\n".join(partes)


TOLERANCIA_CUADRE = 0.5  # pesos: redondeos del sistema


def totales(
    items: list[CotizacionItem], compuestos: list[Compuesto], iva_documento: float | None
) -> dict[str, float | int | None]:
    """Subtotal de mobiliario (con el precio presentado de cada compuesto), cargos, IVA y total.

    El IVA se copia del PDF del sistema; si un compuesto cambió de precio, se ajusta en la misma
    proporción (el sistema lo calcula sobre todo, cargos incluidos).
    """
    partidas = [i for i in sorted(items, key=lambda i: i.orden) if not i.cargo]
    filas = renglones(partidas, compuestos)
    subtotal = round(sum(r.importe for r in filas), 2)
    flete = round(sum(i.importe for i in items if i.cargo == "flete"), 2)
    montaje = round(sum(i.importe for i in items if i.cargo == "montaje"), 2)
    base_documento = sum(i.importe for i in items)
    base = subtotal + flete + montaje
    iva = None
    if iva_documento is not None:
        iva = float(iva_documento)
        if base_documento and abs(base - base_documento) >= 0.005:
            iva = iva * base / base_documento
        iva = round(iva, 2)
    return {
        "subtotal": subtotal,
        "flete": flete,
        "montaje": montaje,
        "iva": iva,
        "total": round(base + (iva or 0), 2),
        # Un compuesto cuenta como un ítem (sus partidas ya no se ven por separado en Revisar).
        "total_items": len(filas),
        "items_pendientes": sum(1 for r in filas if r.primero.estado == "falta_imagen"),
    }


def cuadre(
    items: list[CotizacionItem],
    compuestos: list[Compuesto],
    total_propuesta: float,
    subtotal_documento: float | None,
    iva_documento: float | None,
) -> Cuadre:
    """¿El total de la propuesta es el del PDF del sistema?

    Se compara contra el SubTotal impreso en el PDF (si se leyó) más su IVA; así se detecta tanto un
    compuesto con otro precio como una partida que no se haya leído bien. Sin SubTotal (exports
    viejos o .xlsx) se usa la suma de las partidas leídas.
    """
    suma_partidas = round(sum(i.importe for i in items), 2)
    referencia = subtotal_documento if subtotal_documento is not None else suma_partidas
    total_documento = round(referencia + (iva_documento or 0), 2)
    partidas = [i for i in sorted(items, key=lambda i: i.orden) if not i.cargo]
    ajustes = [
        AjustePrecio(
            compuesto_id=r.compuesto.id,
            nombre=r.compuesto.nombre,
            importe_partidas=r.importe_partidas,
            importe=r.importe,
        )
        for r in renglones(partidas, compuestos)
        if r.compuesto and r.precio_cambiado
    ]
    diferencia = round(total_propuesta - total_documento, 2)
    lectura_ok = subtotal_documento is None or abs(suma_partidas - subtotal_documento) < TOLERANCIA_CUADRE
    return Cuadre(
        cuadra=abs(diferencia) < TOLERANCIA_CUADRE and lectura_ok,
        total_documento=total_documento,
        total_propuesta=round(total_propuesta, 2),
        diferencia=diferencia,
        subtotal_documento=subtotal_documento,
        suma_partidas=suma_partidas,
        ajustes=ajustes,
    )
