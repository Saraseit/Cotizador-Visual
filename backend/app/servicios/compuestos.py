"""Artículos compuestos: varias partidas que se presentan como un solo artículo.

El vendedor los arma en Revisar (p. ej. la cubierta y la base de una mesa). Es sólo presentación: cada
partida conserva su código, cantidad y precio; en los PDF el compuesto ocupa un renglón con su foto y
su nombre, y debajo van sus componentes. El importe del renglón es la suma de los de sus partidas, así
que subtotal y total no cambian.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from app.db.modelos import Compuesto, CotizacionItem, descripcion_impresa

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
    def precio_unitario(self) -> float | None:
        """Precio de un artículo completo: la suma de los unitarios. Sólo tiene sentido con cantidad común."""
        if self.cantidad_comun is None:
            return None
        return round(sum(float(i.precio_unitario) for i in self.items), 2)

    @property
    def importe(self) -> float:
        return round(sum(i.importe for i in self.items), 2)

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
        "Cada imagen adjunta es la foto de una de esas piezas por separado. Combínalas en el artículo "
        "completo, montado como se usa (por ejemplo, la cubierta sobre la base), respetando la forma, el "
        "material, el color y las proporciones de cada pieza. Una sola unidad del artículo.",
    ]
    if peticion.strip():
        partes.append(f"Indicaciones del vendedor: {peticion.strip()}")
    return "\n\n".join(partes)
