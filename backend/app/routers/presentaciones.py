"""Presentación editorial de una cotización: configuración, imágenes por hueco, montajes con IA y PDF."""

import logging
from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import Usuario
from app.config import Configuracion, obtener_configuracion
from app.db.cliente import ClienteDB
from app.db.modelos import (
    HUECOS_AMBIENTACION,
    PREFIJO_MONTAJE,
    AsignarImagenPresentacion,
    ConfigPresentacion,
    ConfigPresentacionEntrada,
    CotizacionDetalle,
    Imagen,
    PeticionMontaje,
    Presentacion,
    ResultadoPdf,
    SeccionVista,
)
from app.routers.catalogo import con_urls
from app.routers.cotizaciones import _fila_cotizacion, _puede_editar, cargar_detalle
from app.routers.imagenes import _verificar_tope_generaciones
from app.servicios import presentacion as servicio
from app.servicios.proveedor_imagenes import ErrorProveedorImagenes, obtener_proveedor
from app.servicios.storage import StorageDep

router = APIRouter(prefix="/cotizaciones", tags=["presentaciones"])
registro = logging.getLogger("cotizador.presentaciones")

Config = Annotated[Configuracion, Depends(obtener_configuracion)]


# ---------------------------------------------------------------------------
# Ayudantes
# ---------------------------------------------------------------------------

async def _fila_presentacion(db: Any, cotizacion_id: UUID) -> dict[str, Any] | None:
    respuesta = await db.table("presentaciones").select("*").eq("cotizacion_id", str(cotizacion_id)).limit(1).execute()
    return respuesta.data[0] if respuesta.data else None


async def _imagenes_por_hueco(db: Any, config: ConfigPresentacion) -> dict[str, dict[str, Any]]:
    """hueco -> fila de `imagenes`. Los huecos cuya imagen ya no existe simplemente no aparecen."""
    ids = {str(i) for i in config.imagenes.values()}
    if not ids:
        return {}
    filas = (await db.table("imagenes").select("*").in_("id", sorted(ids)).execute()).data or []
    por_id = {str(f["id"]): f for f in filas}
    return {hueco: por_id[str(imagen_id)] for hueco, imagen_id in config.imagenes.items() if str(imagen_id) in por_id}


async def _armar(
    db: Any, storage: Any, cotizacion_id: UUID, detalle: CotizacionDetalle | None = None
) -> tuple[Presentacion, CotizacionDetalle, dict[str, dict[str, Any]]]:
    detalle = detalle or await cargar_detalle(db, storage, cotizacion_id)
    fila = await _fila_presentacion(db, cotizacion_id)
    config = servicio.leer_config((fila or {}).get("config"), detalle)
    vistas = servicio.secciones_vista(config, detalle)
    crudas = await _imagenes_por_hueco(db, config)
    con_url: list[Imagen] = await con_urls(storage, list(crudas.values()))
    imagenes = dict(zip(crudas.keys(), con_url))
    presentacion = Presentacion(
        cotizacion_id=cotizacion_id,
        config=config,
        secciones=vistas,
        imagenes=imagenes,
        guardada=fila is not None,
    )
    return presentacion, detalle, crudas


async def _guardar_config(db: Any, cotizacion_id: UUID, config: ConfigPresentacion, usuario: Any) -> None:
    await db.table("presentaciones").upsert(
        {
            "cotizacion_id": str(cotizacion_id),
            "config": config.model_dump(mode="json"),
            "actualizado_por": str(usuario.id),
        },
        on_conflict="cotizacion_id",
    ).execute()


def _validar_hueco(hueco: str, vistas: list[SeccionVista]) -> None:
    if hueco in HUECOS_AMBIENTACION:
        return
    if hueco.startswith(PREFIJO_MONTAJE) and hueco[len(PREFIJO_MONTAJE) :] in {v.clave for v in vistas}:
        return
    raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"El hueco '{hueco}' no existe en esta presentación.")


async def _borrar_montaje_ia(db: Any, storage: Any, imagen_id: UUID | None, cotizacion_id: UUID) -> None:
    """Al reemplazar un montaje generado con IA de esta cotización, se borra para no dejar basura.

    Las imágenes que subió el vendedor (biblioteca de ambientación) nunca se borran aquí.
    """
    if imagen_id is None:
        return
    fila = (await db.table("imagenes").select("*").eq("id", str(imagen_id)).limit(1).execute()).data
    if not fila:
        return
    imagen = fila[0]
    origen = imagen.get("origen") or {}
    if imagen.get("tipo") != "montaje" or str(origen.get("cotizacion_id")) != str(cotizacion_id):
        return
    try:
        await storage.eliminar(storage.bucket_imagenes, imagen["ruta_storage"])
    except HTTPException as error:  # el archivo ya no estaba: la fila se borra igual
        registro.warning("No se pudo borrar el montaje %s de Storage: %s", imagen_id, error.detail)
    await db.table("imagenes").delete().eq("id", str(imagen_id)).execute()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/{cotizacion_id}/presentacion", response_model=Presentacion)
async def obtener_presentacion(cotizacion_id: UUID, usuario: Usuario, db: ClienteDB, storage: StorageDep) -> Presentacion:
    """Configuración guardada (o la de por defecto) más las secciones actuales de la cotización."""
    presentacion, _, _ = await _armar(db, storage, cotizacion_id)
    return presentacion


@router.put("/{cotizacion_id}/presentacion", response_model=Presentacion)
async def guardar_presentacion(
    cotizacion_id: UUID, cuerpo: ConfigPresentacionEntrada, usuario: Usuario, db: ClienteDB, storage: StorageDep
) -> Presentacion:
    """Guarda lo que escribe el vendedor. Las imágenes de cada hueco se asignan por separado."""
    cotizacion = await _fila_cotizacion(db, cotizacion_id, "*")
    _puede_editar(cotizacion, usuario)
    fila = await _fila_presentacion(db, cotizacion_id)
    huecos = ConfigPresentacion.model_validate((fila or {}).get("config") or {}).imagenes if fila else {}
    await _guardar_config(db, cotizacion_id, ConfigPresentacion(**cuerpo.model_dump(), imagenes=huecos), usuario)
    presentacion, _, _ = await _armar(db, storage, cotizacion_id)
    return presentacion


@router.put("/{cotizacion_id}/presentacion/imagenes", response_model=Presentacion)
async def asignar_imagen_presentacion(
    cotizacion_id: UUID, cuerpo: AsignarImagenPresentacion, usuario: Usuario, db: ClienteDB, storage: StorageDep
) -> Presentacion:
    """Pone (o quita con `null`) la imagen de un hueco: portada, manifiesto, cierre o montaje de una sección."""
    cotizacion = await _fila_cotizacion(db, cotizacion_id, "*")
    _puede_editar(cotizacion, usuario)
    presentacion, _, _ = await _armar(db, storage, cotizacion_id)
    _validar_hueco(cuerpo.hueco, presentacion.secciones)

    if cuerpo.imagen_id is not None:
        existe = await db.table("imagenes").select("id").eq("id", str(cuerpo.imagen_id)).limit(1).execute()
        if not existe.data:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "La imagen no existe.")

    config = presentacion.config
    anterior = config.imagenes.get(cuerpo.hueco)
    if cuerpo.imagen_id is None:
        config.imagenes.pop(cuerpo.hueco, None)
    else:
        config.imagenes[cuerpo.hueco] = cuerpo.imagen_id
    await _guardar_config(db, cotizacion_id, config, usuario)
    if anterior and str(anterior) != str(cuerpo.imagen_id):
        await _borrar_montaje_ia(db, storage, anterior, cotizacion_id)

    actualizada, _, _ = await _armar(db, storage, cotizacion_id)
    return actualizada


@router.post("/{cotizacion_id}/presentacion/montajes", response_model=Presentacion)
async def generar_montaje(
    cotizacion_id: UUID,
    cuerpo: PeticionMontaje,
    usuario: Usuario,
    db: ClienteDB,
    storage: StorageDep,
    config_app: Config,
) -> Presentacion:
    """Genera con IA el render de montaje de una sección, usando las fotos de sus piezas como referencia."""
    cotizacion = await _fila_cotizacion(db, cotizacion_id, "*")
    _puede_editar(cotizacion, usuario)
    presentacion, detalle, _ = await _armar(db, storage, cotizacion_id)
    vista = next((v for v in presentacion.secciones if v.clave == cuerpo.clave), None)
    if vista is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Esa sección no está en la cotización.")

    try:
        proveedor = obtener_proveedor(config_app)
    except ErrorProveedorImagenes as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(error)) from error
    await _verificar_tope_generaciones(db, usuario, config_app)

    items = [i for i in sorted(detalle.items, key=lambda i: i.orden) if not i.cargo and i.categoria == vista.clave]
    rutas: list[str] = []
    for item in items:
        if item.imagen and item.imagen.ruta_storage not in rutas:
            rutas.append(item.imagen.ruta_storage)
    referencias = [await storage.descargar(storage.bucket_imagenes, r) for r in rutas[: servicio.REFERENCIAS_MAXIMAS]]

    prompt = servicio.prompt_montaje(presentacion.config, vista, items, cuerpo.indicaciones)
    try:
        imagen_generada = await proveedor.generar_escena(referencias, prompt)
    except ErrorProveedorImagenes as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(error)) from error

    # Se registra sólo cuando el proveedor respondió bien: un fallo no consume cupo.
    await db.table("generaciones").insert(
        {
            "usuario_id": str(usuario.id),
            "cotizacion_id": str(cotizacion_id),
            "peticion": prompt,
            "proveedor": proveedor.nombre,
            "modelo": proveedor.modelo,
            "cantidad": 1,
        }
    ).execute()

    ruta = f"presentaciones/{cotizacion_id}/montaje-{uuid4().hex}.jpg"
    await storage.subir(storage.bucket_imagenes, ruta, servicio.a_jpeg(imagen_generada), "image/jpeg")
    creada = (
        await db.table("imagenes")
        .insert(
            {
                "item_id": None,
                "ruta_storage": ruta,
                "tipo": "montaje",
                "etiquetas": ["montaje", "render conceptual"],
                "origen": {
                    "fuente": "ia_montaje",
                    "cotizacion_id": str(cotizacion_id),
                    "seccion": vista.clave,
                    "peticion": cuerpo.indicaciones,
                    "proveedor": proveedor.nombre,
                    "modelo": proveedor.modelo,
                },
                "subida_por": str(usuario.id),
            }
        )
        .execute()
    ).data[0]

    # Se relee la config: mientras se generaba (puede tardar un minuto) el vendedor pudo guardar textos.
    fila = await _fila_presentacion(db, cotizacion_id)
    config = servicio.leer_config((fila or {}).get("config"), detalle)
    hueco = servicio.hueco_montaje(vista.clave)
    anterior = config.imagenes.get(hueco)
    config.imagenes[hueco] = UUID(str(creada["id"]))
    await _guardar_config(db, cotizacion_id, config, usuario)
    await _borrar_montaje_ia(db, storage, anterior, cotizacion_id)

    actualizada, _, _ = await _armar(db, storage, cotizacion_id)
    return actualizada


@router.post("/{cotizacion_id}/presentacion/pdf", response_model=ResultadoPdf)
async def generar_pdf_presentacion(
    cotizacion_id: UUID, usuario: Usuario, db: ClienteDB, storage: StorageDep
) -> ResultadoPdf:
    """Renderiza la presentación editorial, la guarda en Storage y devuelve una URL firmada."""
    cotizacion = await _fila_cotizacion(db, cotizacion_id, "*")
    _puede_editar(cotizacion, usuario)
    presentacion, detalle, crudas = await _armar(db, storage, cotizacion_id)

    pdf = await servicio.generar_pdf(detalle, presentacion.config, presentacion.secciones, crudas, storage)

    marca = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    ruta = f"cotizaciones/{cotizacion_id}/presentaciones/presentacion-{marca}.pdf"
    await storage.subir(storage.bucket_exports, ruta, pdf, "application/pdf")
    await db.table("cotizaciones").update({"estado": "generada"}).eq("id", str(cotizacion_id)).execute()
    return ResultadoPdf(url=await storage.url_firmada(storage.bucket_exports, ruta), ruta_storage=ruta)
