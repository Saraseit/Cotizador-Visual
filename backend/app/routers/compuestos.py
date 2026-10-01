"""Artículos compuestos de una cotización: combinar partidas, su foto y separarlas.

Es sólo presentación: las partidas conservan código, cantidad y precio; en los PDF salen como un solo
artículo con la foto y el nombre del compuesto (ver `servicios/compuestos.py`).
"""

import logging
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import Usuario
from app.config import Configuracion, obtener_configuracion
from app.db.cliente import ClienteDB
from app.db.modelos import (
    CotizacionDetalle,
    CotizacionItem,
    CrearCompuesto,
    EditarCompuesto,
    PeticionGenerarCompuesto,
    PrecioCompuesto,
    ResultadoGeneracion,
)
from app.routers.catalogo import con_urls
from app.routers.cotizaciones import _fila_cotizacion, _puede_editar, cargar_detalle
from app.routers.imagenes import _verificar_tope_generaciones
from app.servicios.compuestos import nombre_por_defecto, prompt_compuesto
from app.servicios.proveedor_imagenes import ErrorProveedorImagenes, obtener_proveedor
from app.servicios.storage import StorageDep, ruta_imagen_catalogo

router = APIRouter(prefix="/cotizaciones", tags=["compuestos"])
registro = logging.getLogger("cotizador.compuestos")

Config = Annotated[Configuracion, Depends(obtener_configuracion)]

ETIQUETA = "compuesto"


# ---------------------------------------------------------------------------
# Ayudantes
# ---------------------------------------------------------------------------

async def _cotizacion_editable(db: Any, cotizacion_id: UUID, usuario: Any) -> None:
    _puede_editar(await _fila_cotizacion(db, cotizacion_id, "*"), usuario)


async def _compuesto(db: Any, cotizacion_id: UUID, compuesto_id: UUID) -> dict[str, Any]:
    respuesta = (
        await db.table("cotizacion_compuestos")
        .select("*")
        .eq("id", str(compuesto_id))
        .eq("cotizacion_id", str(cotizacion_id))
        .limit(1)
        .execute()
    )
    if not respuesta.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El artículo compuesto no existe en esta cotización.")
    return respuesta.data[0]


def _partidas_de(detalle: CotizacionDetalle, compuesto_id: UUID) -> list[CotizacionItem]:
    return [i for i in detalle.items if i.compuesto_id == compuesto_id]


def _columnas_precio(precio: PrecioCompuesto, partidas: list[CotizacionItem]) -> dict[str, Any]:
    """Columnas de precio del compuesto. La partida cuyo precio se queda tiene que ser del compuesto."""
    if precio.precio_modo == "partida" and precio.precio_item_id not in {p.id for p in partidas}:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "El precio tiene que ser el de una de las partidas del artículo.")
    return {
        "precio_modo": precio.precio_modo,
        "precio_item_id": str(precio.precio_item_id) if precio.precio_modo == "partida" else None,
        "precio_manual": round(precio.precio_manual, 2) if precio.precio_modo == "manual" else None,
    }


async def _imagen(db: Any, imagen_id: UUID) -> dict[str, Any]:
    respuesta = await db.table("imagenes").select("*").eq("id", str(imagen_id)).limit(1).execute()
    if not respuesta.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La imagen no existe.")
    return respuesta.data[0]


async def _juntar_partidas(db: Any, detalle: CotizacionDetalle, ids: list[UUID]) -> None:
    """Deja las partidas del compuesto seguidas, en el lugar de la primera, para que en Revisar se
    vean juntas igual que en el PDF."""
    miembros = set(ids)
    ordenados = sorted(detalle.items, key=lambda i: i.orden)
    del_compuesto = [i.id for i in ordenados if i.id in miembros]
    nuevo: list[UUID] = []
    for item in ordenados:
        if item.id not in miembros:
            nuevo.append(item.id)
        elif item.id == del_compuesto[0]:
            nuevo.extend(del_compuesto)
    if nuevo != [i.id for i in ordenados]:
        await db.rpc("reordenar_cotizacion", {"p_cotizacion": str(detalle.id), "p_ids": [str(i) for i in nuevo]}).execute()


async def _guardar_en_galerias(
    db: Any, storage: Any, imagen: dict[str, Any], partidas: list[CotizacionItem], nombre: str, usuario: Any
) -> int:
    """Copia la foto del artículo completo a la galería de cada SKU del compuesto que aún no la tenga.

    Cada galería recibe su propio archivo (no una fila que apunte al mismo objeto), para que borrar la
    imagen de un SKU nunca deje sin foto al otro. Devuelve cuántas copias se hicieron.
    """
    destinos = {i.item_id for i in partidas if i.item_id}
    if imagen.get("item_id"):
        destinos.discard(UUID(str(imagen["item_id"])))
    if not destinos:
        return 0
    ya_copiadas = (
        await db.table("imagenes").select("item_id").contains("origen", {"copia_de": str(imagen["id"])}).execute()
    ).data or []
    destinos -= {UUID(str(f["item_id"])) for f in ya_copiadas if f.get("item_id")}
    if not destinos:
        return 0

    codigos = {
        str(f["id"]): str(f["codigo"])
        for f in (await db.table("catalogo_items").select("id, codigo").in_("id", sorted(str(d) for d in destinos)).execute()).data
        or []
    }
    datos = await storage.descargar(storage.bucket_imagenes, imagen["ruta_storage"])
    extension = "." + imagen["ruta_storage"].rsplit(".", 1)[-1] if "." in imagen["ruta_storage"] else ".png"
    tipo_mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(extension.lower(), "image/png")
    filas = []
    for item_id in sorted(destinos, key=str):
        ruta = ruta_imagen_catalogo(codigos.get(str(item_id)), f"{uuid4().hex}{extension}", subcarpeta="compuestos")
        await storage.subir(storage.bucket_imagenes, ruta, datos, tipo_mime)
        filas.append(
            {
                "item_id": str(item_id),
                "ruta_storage": ruta,
                "tipo": imagen["tipo"],
                "etiquetas": sorted(set(imagen.get("etiquetas") or []) | {ETIQUETA}),
                "origen": {**(imagen.get("origen") or {}), "copia_de": str(imagen["id"]), "compuesto": nombre},
                "subida_por": str(usuario.id),
            }
        )
    await db.table("imagenes").insert(filas).execute()
    # La original también queda marcada como foto de artículo compuesto.
    if ETIQUETA not in (imagen.get("etiquetas") or []):
        await (
            db.table("imagenes")
            .update({"etiquetas": sorted(set(imagen.get("etiquetas") or []) | {ETIQUETA})})
            .eq("id", str(imagen["id"]))
            .execute()
        )
    return len(filas)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/{cotizacion_id}/compuestos", response_model=CotizacionDetalle, status_code=status.HTTP_201_CREATED)
async def crear_compuesto(
    cotizacion_id: UUID, cuerpo: CrearCompuesto, usuario: Usuario, db: ClienteDB, storage: StorageDep
) -> CotizacionDetalle:
    """Combina partidas en un artículo compuesto. Sus partidas no cambian; el precio que se presenta
    es la suma de ellas, el de una de ellas o uno escrito por el vendedor (`precio`)."""
    await _cotizacion_editable(db, cotizacion_id, usuario)
    detalle = await cargar_detalle(db, storage, cotizacion_id)
    ids = list(dict.fromkeys(cuerpo.item_ids))
    if len(ids) < 2:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Elige al menos dos partidas para combinar.")
    por_id = {i.id: i for i in detalle.items}
    if any(i not in por_id for i in ids):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Hay partidas que no pertenecen a esta cotización.")
    partidas = sorted((por_id[i] for i in ids), key=lambda i: i.orden)
    if any(p.cargo for p in partidas):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Flete y montaje no se pueden combinar en un artículo.")
    if any(p.compuesto_id for p in partidas):
        raise HTTPException(status.HTTP_409_CONFLICT, "Alguna de las partidas ya es parte de otro artículo compuesto.")

    imagen_id = cuerpo.imagen_id or next((p.imagen_id for p in partidas if p.imagen_id), None)
    if cuerpo.imagen_id:
        await _imagen(db, cuerpo.imagen_id)

    creado = (
        await db.table("cotizacion_compuestos")
        .insert(
            {
                "cotizacion_id": str(cotizacion_id),
                "nombre": cuerpo.nombre.strip() or nombre_por_defecto(partidas),
                "imagen_id": str(imagen_id) if imagen_id else None,
                **_columnas_precio(cuerpo.precio, partidas),
            }
        )
        .execute()
    )
    compuesto_id = creado.data[0]["id"]
    await (
        db.table("cotizacion_items")
        .update({"compuesto_id": compuesto_id})
        .in_("id", [str(p.id) for p in partidas])
        .eq("cotizacion_id", str(cotizacion_id))
        .execute()
    )
    await _juntar_partidas(db, detalle, [p.id for p in partidas])
    return await cargar_detalle(db, storage, cotizacion_id)


@router.patch("/{cotizacion_id}/compuestos/{compuesto_id}", response_model=CotizacionDetalle)
async def editar_compuesto(
    cotizacion_id: UUID,
    compuesto_id: UUID,
    cuerpo: EditarCompuesto,
    usuario: Usuario,
    db: ClienteDB,
    storage: StorageDep,
) -> CotizacionDetalle:
    """Cambia el nombre, la foto o el precio del compuesto.

    Con `guardar_en_galerias` la foto (una subida o un render con IA del artículo completo) se copia
    también a la galería de cada SKU del compuesto.
    """
    await _cotizacion_editable(db, cotizacion_id, usuario)
    await _compuesto(db, cotizacion_id, compuesto_id)
    detalle = await cargar_detalle(db, storage, cotizacion_id)
    partidas = _partidas_de(detalle, compuesto_id)

    cambios: dict[str, Any] = {}
    if cuerpo.nombre is not None:
        cambios["nombre"] = cuerpo.nombre.strip() or nombre_por_defecto(partidas)
    if cuerpo.precio is not None:
        cambios.update(_columnas_precio(cuerpo.precio, partidas))
    if "imagen_id" in cuerpo.model_fields_set:
        cambios["imagen_id"] = str(cuerpo.imagen_id) if cuerpo.imagen_id else None
        if cuerpo.imagen_id:
            imagen = await _imagen(db, cuerpo.imagen_id)
            if cuerpo.guardar_en_galerias:
                nombre = cambios.get("nombre") or next((c.nombre for c in detalle.compuestos if c.id == compuesto_id), "")
                await _guardar_en_galerias(db, storage, imagen, partidas, nombre, usuario)
    if cambios:
        await db.table("cotizacion_compuestos").update(cambios).eq("id", str(compuesto_id)).execute()
    return await cargar_detalle(db, storage, cotizacion_id)


@router.delete("/{cotizacion_id}/compuestos/{compuesto_id}", response_model=CotizacionDetalle)
async def separar_compuesto(
    cotizacion_id: UUID, compuesto_id: UUID, usuario: Usuario, db: ClienteDB, storage: StorageDep
) -> CotizacionDetalle:
    """Deshace el compuesto: sus partidas vuelven a imprimirse sueltas, cada una con su foto.

    La foto del compuesto se queda en la biblioteca.
    """
    await _cotizacion_editable(db, cotizacion_id, usuario)
    await _compuesto(db, cotizacion_id, compuesto_id)
    await db.table("cotizacion_items").update({"compuesto_id": None}).eq("compuesto_id", str(compuesto_id)).execute()
    await db.table("cotizacion_compuestos").delete().eq("id", str(compuesto_id)).execute()
    return await cargar_detalle(db, storage, cotizacion_id)


@router.post("/{cotizacion_id}/compuestos/{compuesto_id}/generar", response_model=ResultadoGeneracion)
async def generar_imagen_compuesto(
    cotizacion_id: UUID,
    compuesto_id: UUID,
    cuerpo: PeticionGenerarCompuesto,
    usuario: Usuario,
    db: ClienteDB,
    storage: StorageDep,
    config: Config,
) -> ResultadoGeneracion:
    """Genera con IA opciones de foto del artículo completo a partir de las fotos de sus partidas.

    Las opciones quedan en la biblioteca del primer SKU; al elegir una (PATCH con
    `guardar_en_galerias`) se copia a la de los demás, y las descartadas se borran desde el cliente.
    """
    await _cotizacion_editable(db, cotizacion_id, usuario)
    compuesto = await _compuesto(db, cotizacion_id, compuesto_id)
    detalle = await cargar_detalle(db, storage, cotizacion_id)
    partidas = _partidas_de(detalle, compuesto_id)
    con_foto = [p for p in partidas if p.imagen]
    if not con_foto:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Ninguna de las partidas tiene foto. Asigna al menos una para generar el artículo completo con IA.",
        )

    try:
        proveedor = obtener_proveedor(config)
    except ErrorProveedorImagenes as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(error)) from error
    await _verificar_tope_generaciones(db, usuario, config)

    referencias = [await storage.descargar(storage.bucket_imagenes, p.imagen.ruta_storage) for p in con_foto if p.imagen]
    peticion = prompt_compuesto(partidas, compuesto.get("nombre") or nombre_por_defecto(partidas), cuerpo.peticion)
    try:
        variantes = await proveedor.generar_compuesto(referencias, peticion, config.variantes_por_generacion)
    except ErrorProveedorImagenes as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(error)) from error

    base_id = str(con_foto[0].imagen_id)
    await db.table("generaciones").insert(
        {
            "usuario_id": str(usuario.id),
            "cotizacion_id": str(cotizacion_id),
            "imagen_base_id": base_id,
            "peticion": cuerpo.peticion or "artículo compuesto",
            "proveedor": proveedor.nombre,
            "modelo": proveedor.modelo,
            "cantidad": len(variantes),
        }
    ).execute()

    # Quedan en la galería del primer SKU de catálogo; si todas son ad hoc, como imágenes sueltas.
    duena = next((p for p in partidas if p.item_id), None)
    codigo = duena.item.codigo if duena and duena.item else (duena.codigo_origen if duena else None)
    filas = []
    for datos in variantes:
        ruta = ruta_imagen_catalogo(codigo, f"{uuid4().hex}.png", subcarpeta="generadas")
        await storage.subir(storage.bucket_imagenes, ruta, datos, "image/png")
        filas.append(
            {
                "item_id": str(duena.item_id) if duena else None,
                "ruta_storage": ruta,
                "tipo": "generada",
                "etiquetas": ["render conceptual", ETIQUETA],
                "origen": {
                    "peticion": cuerpo.peticion,
                    "imagenes_base_ids": [str(p.imagen_id) for p in con_foto],
                    "imagen_base_id": base_id,
                    "compuesto_id": str(compuesto_id),
                    "proveedor": proveedor.nombre,
                    "modelo": proveedor.modelo,
                },
                "subida_por": str(usuario.id),
            }
        )
    creadas = await db.table("imagenes").insert(filas).execute()
    return ResultadoGeneracion(imagenes=await con_urls(storage, creadas.data or []))
