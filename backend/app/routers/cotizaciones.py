"""Cotizaciones: subir export, listar, ver detalle, asignar imágenes y generar el PDF."""

from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.auth import Usuario, UsuarioActual
from app.config import Configuracion, obtener_configuracion
from app.db.cliente import ClienteDB
from app.db.modelos import (
    AsignarImagen,
    CotizacionDetalle,
    CotizacionItem,
    CotizacionResumen,
    ResultadoPdf,
    calcular_estado_item,
)
from app.servicios import render_pdf
from app.servicios.matching import (
    agrupar_imagenes,
    indexar_catalogo,
    normalizar_codigo,
    resolver_filas,
)
from app.servicios.parser_export import ErrorParser, cargar_mapeo, leer_export
from app.servicios.storage import StorageDep, nombre_seguro

router = APIRouter(prefix="/cotizaciones", tags=["cotizaciones"])

Config = Annotated[Configuracion, Depends(obtener_configuracion)]

SELECT_DETALLE = "*, cotizacion_items(*, imagen:imagenes(*), item:catalogo_items(*))"
SELECT_RESUMEN = "*, cotizacion_items(id, imagen_id)"


# ---------------------------------------------------------------------------
# Ayudantes
# ---------------------------------------------------------------------------

def _puede_editar(cotizacion: dict[str, Any], usuario: UsuarioActual) -> None:
    if str(cotizacion.get("creado_por")) != str(usuario.id) and not usuario.es_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sólo quien creó la cotización (o un admin) puede editarla.")


async def _fila_cotizacion(db: Any, cotizacion_id: UUID, seleccion: str = SELECT_DETALLE) -> dict[str, Any]:
    respuesta = await db.table("cotizaciones").select(seleccion).eq("id", str(cotizacion_id)).limit(1).execute()
    if not respuesta.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La cotización no existe.")
    return respuesta.data[0]


def _resumen_desde_fila(fila: dict[str, Any]) -> CotizacionResumen:
    items = fila.get("cotizacion_items") or []
    datos = {k: v for k, v in fila.items() if k != "cotizacion_items"}
    return CotizacionResumen(
        **datos,
        total_items=len(items),
        items_pendientes=sum(1 for i in items if not i.get("imagen_id")),
    )


async def _armar_detalle(fila: dict[str, Any], storage: Any) -> CotizacionDetalle:
    crudos = sorted(fila.get("cotizacion_items") or [], key=lambda i: (i.get("orden", 0), i.get("creado_en", "")))
    rutas = [i["imagen"]["ruta_storage"] for i in crudos if i.get("imagen")]
    urls = await storage.urls_firmadas(storage.bucket_imagenes, rutas)

    items: list[CotizacionItem] = []
    for crudo in crudos:
        datos = dict(crudo)
        imagen = datos.pop("imagen", None)
        item = datos.pop("item", None)
        if imagen:
            imagen["url"] = urls.get(imagen["ruta_storage"])
        cantidad = float(datos.get("cantidad") or 0)
        precio = float(datos.get("precio_unitario") or 0)
        items.append(
            CotizacionItem(
                **datos,
                imagen=imagen,
                item=item,
                estado=calcular_estado_item(imagen),
                importe=round(cantidad * precio, 2),
            )
        )

    encabezado = {k: v for k, v in fila.items() if k != "cotizacion_items"}
    return CotizacionDetalle(
        **encabezado,
        items=items,
        total=round(sum(i.importe for i in items), 2),
        total_items=len(items),
        items_pendientes=sum(1 for i in items if i.estado == "falta_imagen"),
    )


async def cargar_detalle(db: Any, storage: Any, cotizacion_id: UUID) -> CotizacionDetalle:
    return await _armar_detalle(await _fila_cotizacion(db, cotizacion_id), storage)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=CotizacionDetalle, status_code=status.HTTP_201_CREATED)
async def crear_cotizacion(
    archivo: UploadFile, usuario: Usuario, db: ClienteDB, storage: StorageDep, config: Config
) -> CotizacionDetalle:
    """Recibe el export del sistema, crea la cotización y sus ítems, y resuelve imágenes."""
    contenido = await archivo.read()
    if not contenido:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El archivo está vacío.")

    try:
        mapeo = cargar_mapeo(config.ruta_mapeo_columnas)
        export = leer_export(contenido, archivo.filename or "", mapeo)
    except ErrorParser as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error
    if not export.filas:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "El archivo no contiene ítems.")

    # --- Matching contra el catálogo ---------------------------------------
    codigos = sorted({normalizar_codigo(f.codigo) for f in export.filas if f.codigo})
    catalogo: dict[str, dict[str, Any]] = {}
    imagenes_por_item: dict[str, list[dict[str, Any]]] = {}
    if codigos:
        respuesta = await db.table("catalogo_items").select("*").in_("codigo", codigos).execute()
        catalogo = indexar_catalogo(respuesta.data or [])
    if catalogo:
        ids = [i["id"] for i in catalogo.values()]
        respuesta = (
            await db.table("imagenes")
            .select("*")
            .in_("item_id", ids)
            .in_("tipo", ["oficial", "variante"])
            .execute()
        )
        imagenes_por_item = agrupar_imagenes(respuesta.data or [])
    resultados = resolver_filas([f.codigo for f in export.filas], catalogo, imagenes_por_item)

    # --- Cotización ----------------------------------------------------------
    creada = (
        await db.table("cotizaciones")
        .insert(
            {
                "nombre_cliente": export.nombre_cliente or "Cliente sin nombre",
                "referencia_externa": export.referencia_externa,
                "creado_por": str(usuario.id),
                "estado": "revision",
            }
        )
        .execute()
    )
    cotizacion = creada.data[0]
    cotizacion_id = cotizacion["id"]

    ruta_export = f"cotizaciones/{cotizacion_id}/origen/{nombre_seguro(archivo.filename, 'export')}"
    await storage.subir(
        storage.bucket_exports, ruta_export, contenido, archivo.content_type or "application/octet-stream"
    )
    await db.table("cotizaciones").update({"archivo_origen_ruta": ruta_export}).eq("id", cotizacion_id).execute()

    filas = [
        {
            "cotizacion_id": cotizacion_id,
            "item_id": resultado.item_id,
            "codigo_origen": fila.codigo,
            "descripcion_origen": fila.descripcion,
            "cantidad": str(fila.cantidad),
            "precio_unitario": str(fila.precio_unitario),
            "imagen_id": resultado.imagen_id,
            "tipo_item": resultado.tipo_item,
            "orden": fila.orden,
        }
        for fila, resultado in zip(export.filas, resultados)
    ]
    await db.table("cotizacion_items").insert(filas).execute()

    return await cargar_detalle(db, storage, UUID(cotizacion_id))


@router.get("", response_model=list[CotizacionResumen])
async def listar_cotizaciones(usuario: Usuario, db: ClienteDB) -> list[CotizacionResumen]:
    """Cotizaciones del usuario; un admin ve todas."""
    consulta = db.table("cotizaciones").select(SELECT_RESUMEN).order("creado_en", desc=True).limit(100)
    if not usuario.es_admin:
        consulta = consulta.eq("creado_por", str(usuario.id))
    respuesta = await consulta.execute()
    return [_resumen_desde_fila(f) for f in respuesta.data or []]


@router.get("/{cotizacion_id}", response_model=CotizacionDetalle)
async def obtener_cotizacion(cotizacion_id: UUID, usuario: Usuario, db: ClienteDB, storage: StorageDep) -> CotizacionDetalle:
    return await cargar_detalle(db, storage, cotizacion_id)


@router.patch("/{cotizacion_id}/items/{item_id}", response_model=CotizacionDetalle)
async def asignar_imagen(
    cotizacion_id: UUID,
    item_id: UUID,
    cuerpo: AsignarImagen,
    usuario: Usuario,
    db: ClienteDB,
    storage: StorageDep,
) -> CotizacionDetalle:
    """Asigna (o quita) la imagen de un ítem. El trigger de BD incrementa `usos` y marca render conceptual."""
    cotizacion = await _fila_cotizacion(db, cotizacion_id, "*")
    _puede_editar(cotizacion, usuario)

    existe = (
        await db.table("cotizacion_items")
        .select("id")
        .eq("id", str(item_id))
        .eq("cotizacion_id", str(cotizacion_id))
        .limit(1)
        .execute()
    )
    if not existe.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El ítem no pertenece a esta cotización.")

    if cuerpo.imagen_id is not None:
        imagen = await db.table("imagenes").select("id").eq("id", str(cuerpo.imagen_id)).limit(1).execute()
        if not imagen.data:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "La imagen no existe.")

    await (
        db.table("cotizacion_items")
        .update({"imagen_id": str(cuerpo.imagen_id) if cuerpo.imagen_id else None})
        .eq("id", str(item_id))
        .execute()
    )
    return await cargar_detalle(db, storage, cotizacion_id)


@router.post("/{cotizacion_id}/generar", response_model=ResultadoPdf)
async def generar_propuesta(
    cotizacion_id: UUID, usuario: Usuario, db: ClienteDB, storage: StorageDep
) -> ResultadoPdf:
    """Renderiza el PDF de la propuesta, lo guarda en Storage y devuelve una URL firmada."""
    fila = await _fila_cotizacion(db, cotizacion_id)
    _puede_editar(fila, usuario)
    detalle = await _armar_detalle(fila, storage)

    pdf = await render_pdf.generar_pdf_cotizacion(detalle, storage)

    marca = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    ruta = f"cotizaciones/{cotizacion_id}/propuestas/propuesta-{marca}.pdf"
    await storage.subir(storage.bucket_exports, ruta, pdf, "application/pdf")
    await db.table("cotizaciones").update({"estado": "generada"}).eq("id", str(cotizacion_id)).execute()

    url = await storage.url_firmada(storage.bucket_exports, ruta)
    return ResultadoPdf(url=url, ruta_storage=ruta)
