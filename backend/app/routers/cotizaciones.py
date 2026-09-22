"""Cotizaciones: subir export, listar, ver detalle, asignar imágenes y generar el PDF."""

import asyncio
import logging
from dataclasses import replace
from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.auth import Usuario, UsuarioActual
from app.config import Configuracion, obtener_configuracion
from app.db.cliente import ClienteDB
from app.db.modelos import (
    AsignarCargo,
    AsignarImagen,
    CotizacionDetalle,
    CotizacionItem,
    CotizacionResumen,
    PdfGenerado,
    Reordenar,
    ResultadoPdf,
    calcular_estado_item,
)
from app.servicios import render_pdf
from app.servicios.cargos import clasificar_cargo
from app.servicios.fotos_pdf import extraer_fotos_partidas, guardar_en_biblioteca
from app.servicios.matching import (
    agrupar_imagenes,
    indexar_catalogo,
    normalizar_codigo,
    resolver_filas,
)
from app.servicios.parser_export import ErrorParser, cargar_mapeo, leer_export
from app.servicios.storage import StorageDep, nombre_seguro

router = APIRouter(prefix="/cotizaciones", tags=["cotizaciones"])
registro = logging.getLogger("cotizador.cotizaciones")

Config = Annotated[Configuracion, Depends(obtener_configuracion)]

SELECT_DETALLE = "*, cotizacion_items(*, imagen:imagenes(*), item:catalogo_items(*))"
SELECT_RESUMEN = "*, cotizacion_items(id, imagen_id, cargo)"


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
    items = [i for i in fila.get("cotizacion_items") or [] if not i.get("cargo")]
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
    return CotizacionDetalle(**encabezado, items=items, **calcular_totales(items, fila.get("iva_documento")))


def calcular_totales(items: list[CotizacionItem], iva_documento: Any) -> dict[str, Any]:
    """Subtotal de mobiliario, cargos por tipo, IVA del documento y total.

    El IVA se copia del PDF del sistema (lo calcula sobre todo, cargos incluidos); si el PDF sólo
    dice "más IVA" queda en None y el total no lo incluye.
    """
    partidas = [i for i in items if not i.cargo]
    subtotal = round(sum(i.importe for i in partidas), 2)
    flete = round(sum(i.importe for i in items if i.cargo == "flete"), 2)
    montaje = round(sum(i.importe for i in items if i.cargo == "montaje"), 2)
    iva = round(float(iva_documento), 2) if iva_documento is not None else None
    return {
        "subtotal": subtotal,
        "flete": flete,
        "montaje": montaje,
        "iva": iva,
        "total": round(subtotal + flete + montaje + (iva or 0), 2),
        "total_items": len(partidas),
        "items_pendientes": sum(1 for i in partidas if i.estado == "falta_imagen"),
    }


async def cargar_detalle(db: Any, storage: Any, cotizacion_id: UUID) -> CotizacionDetalle:
    return await _armar_detalle(await _fila_cotizacion(db, cotizacion_id), storage)


async def registrar_pdf(db: Any, cotizacion_id: UUID, tipo: str, ruta: str, usuario_id: UUID) -> None:
    """Deja constancia de un PDF recién generado (propuesta base o presentación editorial), para
    que la pantalla Propuestas pueda listar el historial. La usan `generar_propuesta` (este router)
    y `generar_pdf_presentacion` (`routers/presentaciones.py`)."""
    await db.table("cotizacion_pdfs").insert(
        {"cotizacion_id": str(cotizacion_id), "tipo": tipo, "ruta_storage": ruta, "generado_por": str(usuario_id)}
    ).execute()


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
    # --- Fotos del PDF a la biblioteca ----------------------------------------
    # Se guardan antes del matching para que las partidas reciban su foto en esta misma subida.
    # Un problema con las fotos nunca impide crear la cotización.
    fotos_importadas, foto_por_orden = 0, {}
    if (archivo.filename or "").lower().endswith(".pdf"):
        try:
            fotos = await asyncio.to_thread(extraer_fotos_partidas, contenido, export.filas)
            fotos_importadas, foto_por_orden = await guardar_en_biblioteca(
                db,
                storage,
                export.filas,
                resolver_filas([f.codigo for f in export.filas], catalogo, imagenes_por_item),
                catalogo,
                imagenes_por_item,
                fotos,
                str(usuario.id),
                export.referencia_externa,
            )
        except Exception:
            registro.exception("No se pudieron guardar las fotos del PDF %s", archivo.filename)

    resultados = resolver_filas([f.codigo for f in export.filas], catalogo, imagenes_por_item)
    # Las partidas fuera de catálogo no tienen biblioteca: reciben directamente la foto que traían.
    resultados = [
        replace(r, imagen_id=foto_por_orden[f.orden]) if r.tipo_item == "ad_hoc" and f.orden in foto_por_orden else r
        for f, r in zip(export.filas, resultados)
    ]

    # --- Cotización ----------------------------------------------------------
    creada = (
        await db.table("cotizaciones")
        .insert(
            {
                "nombre_cliente": export.nombre_cliente or "Cliente sin nombre",
                "referencia_externa": export.referencia_externa,
                "creado_por": str(usuario.id),
                "estado": "revision",
                "iva_documento": str(export.iva) if export.iva is not None else None,
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
            "categoria": fila.categoria or "",
            "cargo": clasificar_cargo(fila.descripcion, fila.categoria),
        }
        for fila, resultado in zip(export.filas, resultados)
    ]
    await db.table("cotizacion_items").insert(filas).execute()

    detalle = await cargar_detalle(db, storage, UUID(cotizacion_id))
    detalle.fotos_importadas = fotos_importadas
    return detalle


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


@router.get("/{cotizacion_id}/pdfs", response_model=list[PdfGenerado])
async def listar_pdfs(cotizacion_id: UUID, usuario: Usuario, db: ClienteDB, storage: StorageDep) -> list[PdfGenerado]:
    """PDF generados de esta cotización (propuesta base y presentación editorial), más recientes primero.

    Para la pantalla Propuestas: ahí se ve de un vistazo si ya hay algo listo para imprimir, aunque se
    haya generado más de una vez o en los dos formatos.
    """
    await _fila_cotizacion(db, cotizacion_id, "id")
    respuesta = (
        await db.table("cotizacion_pdfs")
        .select("*")
        .eq("cotizacion_id", str(cotizacion_id))
        .order("creado_en", desc=True)
        .execute()
    )
    filas = respuesta.data or []
    rutas = [f["ruta_storage"] for f in filas]
    urls, urls_descarga = await asyncio.gather(
        storage.urls_firmadas(storage.bucket_exports, rutas),
        storage.urls_firmadas(storage.bucket_exports, rutas, descarga=True),
    )
    return [
        PdfGenerado(
            id=f["id"],
            tipo=f["tipo"],
            creado_en=f["creado_en"],
            url=urls.get(f["ruta_storage"]),
            url_descarga=urls_descarga.get(f["ruta_storage"]),
        )
        for f in filas
    ]


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
    await registrar_pdf(db, cotizacion_id, "base", ruta, usuario.id)

    url = await storage.url_firmada(storage.bucket_exports, ruta)
    return ResultadoPdf(url=url, ruta_storage=ruta)


@router.put("/{cotizacion_id}/orden", response_model=CotizacionDetalle)
async def reordenar_partidas(
    cotizacion_id: UUID, cuerpo: Reordenar, usuario: Usuario, db: ClienteDB, storage: StorageDep
) -> CotizacionDetalle:
    """Guarda el orden en que se imprimirán las partidas (lo arma el vendedor arrastrando en Revisar)."""
    cotizacion = await _fila_cotizacion(db, cotizacion_id, "*")
    _puede_editar(cotizacion, usuario)
    propias = await db.table("cotizacion_items").select("id").eq("cotizacion_id", str(cotizacion_id)).execute()
    ids_propios = {str(f["id"]) for f in propias.data or []}
    ajenos = [str(i) for i in cuerpo.ids if str(i) not in ids_propios]
    if ajenos:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Hay partidas que no pertenecen a esta cotización.")
    await db.rpc("reordenar_cotizacion", {"p_cotizacion": str(cotizacion_id), "p_ids": [str(i) for i in cuerpo.ids]}).execute()
    return await cargar_detalle(db, storage, cotizacion_id)


@router.put("/{cotizacion_id}/items/{item_id}/cargo", response_model=CotizacionDetalle)
async def asignar_cargo(
    cotizacion_id: UUID, item_id: UUID, cuerpo: AsignarCargo, usuario: Usuario, db: ClienteDB, storage: StorageDep
) -> CotizacionDetalle:
    """Marca una partida como flete o montaje (o la devuelve a mobiliario con `null`)."""
    cotizacion = await _fila_cotizacion(db, cotizacion_id, "*")
    _puede_editar(cotizacion, usuario)
    actualizado = (
        await db.table("cotizacion_items")
        .update({"cargo": cuerpo.cargo})
        .eq("id", str(item_id))
        .eq("cotizacion_id", str(cotizacion_id))
        .execute()
    )
    if not actualizado.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El ítem no pertenece a esta cotización.")
    return await cargar_detalle(db, storage, cotizacion_id)
