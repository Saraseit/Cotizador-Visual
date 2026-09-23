"""Presentación editorial de una cotización: configuración, imágenes por hueco, montajes con IA y PDF."""

import logging
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

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
    FormatoPropuesta,
    Imagen,
    PeticionMontaje,
    Presentacion,
    ResultadoPdf,
    SeccionVista,
)
from app.routers.catalogo import con_urls
from app.routers.cotizaciones import _fila_cotizacion, _puede_editar, cargar_detalle, registrar_pdf
from app.routers.imagenes import _verificar_tope_generaciones
from app.servicios import presentacion as servicio
from app.servicios.ia_texto import ErrorIaTexto, traducir
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


async def asegurar_traducciones(
    db: Any,
    cotizacion_id: UUID,
    detalle: CotizacionDetalle,
    config: ConfigPresentacion,
    config_app: Configuracion,
    usuario: Any,
    obligatoria: bool = False,
) -> ConfigPresentacion:
    """Traduce con IA lo que falte y lo guarda en la caché de la presentación.

    Se paga una sola vez por texto. Si la IA falla y la traducción no era obligatoria, el PDF sale
    con el glosario en vez de quedarse en español a medias.
    """
    if config.idioma == "es":
        return config
    vistas = servicio.secciones_vista(config, detalle)
    faltantes = [t for t in servicio.textos_traducibles(detalle, config, vistas) if t not in config.traducciones]
    if not faltantes:
        return config
    try:
        nuevas = await traducir(faltantes, config.idioma, config_app)
    except ErrorIaTexto as error:
        if obligatoria:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(error)) from error
        registro.warning("Sin traducción con IA (%s): el PDF sale con el glosario.", error)
        return config
    config.traducciones.update(nuevas)
    await _guardar_config(db, cotizacion_id, config, usuario)
    return config


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
    # Del guardado anterior se conservan las imágenes de cada hueco y las traducciones ya pagadas;
    # el resto lo manda el cuerpo.
    huecos: dict[str, UUID] = {}
    traducciones: dict[str, str] = {}
    try:
        anterior = ConfigPresentacion.model_validate(servicio.migrar_config((fila or {}).get("config") or {}))
        huecos, traducciones = anterior.imagenes, anterior.traducciones
    except ValidationError:
        registro.warning("La config guardada de %s no es válida: se guarda sin imágenes.", cotizacion_id)
    nueva = ConfigPresentacion(**cuerpo.model_dump(), imagenes=huecos, traducciones=traducciones)
    await _guardar_config(db, cotizacion_id, nueva, usuario)
    presentacion, _, _ = await _armar(db, storage, cotizacion_id)
    return presentacion


@router.put("/{cotizacion_id}/presentacion/formato", response_model=Presentacion)
async def guardar_formato(
    cotizacion_id: UUID, cuerpo: FormatoPropuesta, usuario: Usuario, db: ClienteDB, storage: StorageDep
) -> Presentacion:
    """Moneda e idioma de los dos PDF, sin tocar el resto de la presentación.

    Lo usa Revisar: ahí el vendedor comprueba los importes convertidos y los textos traducidos antes
    de imprimir, sin tener que entrar al editor de la presentación.
    """
    cotizacion = await _fila_cotizacion(db, cotizacion_id, "*")
    _puede_editar(cotizacion, usuario)
    presentacion, _, _ = await _armar(db, storage, cotizacion_id)
    config = presentacion.config
    config.moneda, config.tipo_cambio, config.idioma = cuerpo.moneda, cuerpo.tipo_cambio, cuerpo.idioma
    await _guardar_config(db, cotizacion_id, config, usuario)
    actualizada, _, _ = await _armar(db, storage, cotizacion_id)
    return actualizada


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
    inspiraciones = await _inspiraciones(db, storage, presentacion.config.plantilla_id)
    referencias += inspiraciones

    prompt = servicio.prompt_montaje(presentacion.config, vista, items, cuerpo.indicaciones, len(inspiraciones))
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


async def _inspiraciones(db: Any, storage: Any, plantilla_id: UUID | None) -> list[bytes]:
    """Imágenes de la plantilla aplicada; se mandan al final para que la IA copie de ellas la atmósfera."""
    if plantilla_id is None:
        return []
    fila = (await db.table("plantillas").select("config").eq("id", str(plantilla_id)).limit(1).execute()).data
    ids = ((fila[0].get("config") if fila else None) or {}).get("inspiraciones") or []
    if not ids:
        return []
    imagenes = (
        await db.table("imagenes").select("ruta_storage").in_("id", ids[: servicio.INSPIRACIONES_MAXIMAS]).execute()
    ).data or []
    descargadas: list[bytes] = []
    for imagen in imagenes:
        try:
            descargadas.append(await storage.descargar(storage.bucket_imagenes, imagen["ruta_storage"]))
        except HTTPException as error:
            registro.warning("No se pudo leer la inspiración %s: %s", imagen["ruta_storage"], error.detail)
    return descargadas


@router.post("/{cotizacion_id}/presentacion/traducir", response_model=Presentacion)
async def traducir_presentacion(
    cotizacion_id: UUID, usuario: Usuario, db: ClienteDB, storage: StorageDep, config_app: Config
) -> Presentacion:
    """Traduce con IA los textos de la cotización al idioma elegido y guarda el resultado.

    Lo que el vendedor ya ajustó a mano en Revisar no se toca.
    """
    cotizacion = await _fila_cotizacion(db, cotizacion_id, "*")
    _puede_editar(cotizacion, usuario)
    presentacion, detalle, _ = await _armar(db, storage, cotizacion_id)
    if presentacion.config.idioma == "es":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "La presentación ya está en español.")
    await asegurar_traducciones(db, cotizacion_id, detalle, presentacion.config, config_app, usuario, obligatoria=True)
    actualizada, _, _ = await _armar(db, storage, cotizacion_id)
    return actualizada


@router.post("/{cotizacion_id}/presentacion/pdf", response_model=ResultadoPdf)
async def generar_pdf_presentacion(
    cotizacion_id: UUID, usuario: Usuario, db: ClienteDB, storage: StorageDep, config_app: Config
) -> ResultadoPdf:
    """Renderiza la presentación editorial, la guarda en Storage y devuelve una URL firmada."""
    cotizacion = await _fila_cotizacion(db, cotizacion_id, "*")
    _puede_editar(cotizacion, usuario)
    presentacion, detalle, crudas = await _armar(db, storage, cotizacion_id)
    config = await asegurar_traducciones(db, cotizacion_id, detalle, presentacion.config, config_app, usuario)

    pdf = await servicio.generar_pdf(detalle, config, presentacion.secciones, crudas, storage)

    marca = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    ruta = f"cotizaciones/{cotizacion_id}/presentaciones/presentacion-{marca}.pdf"
    await storage.subir(storage.bucket_exports, ruta, pdf, "application/pdf")
    await db.table("cotizaciones").update({"estado": "generada"}).eq("id", str(cotizacion_id)).execute()
    await registrar_pdf(db, cotizacion_id, "editorial", ruta, usuario.id)
    return ResultadoPdf(url=await storage.url_firmada(storage.bucket_exports, ruta), ruta_storage=ruta)
