"""Plantillas de presentación (nacen de una inspiración) y paletas guardadas.

El vendedor sube una imagen que le gusta; la IA la mira y propone composición, tipografía, tamaño de
títulos, piezas por página y paleta. Si la IA no está disponible, la paleta se saca de la imagen con
análisis local y el resto queda en los valores de la presentación de ejemplo. Después el vendedor
ajusta lo que quiera: la plantilla es sólo un punto de partida reutilizable.
"""

import logging
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status

from app.auth import Usuario
from app.config import Configuracion, obtener_configuracion
from app.db.cliente import ClienteDB
from app.db.modelos import (
    Imagen,
    PaletaEntrada,
    PaletaGuardada,
    ParametrosPlantilla,
    Plantilla,
    PlantillaActualizacion,
)
from app.routers.catalogo import con_urls
from app.routers.imagenes import TAMANO_MAXIMO, TIPOS_PERMITIDOS
from app.servicios import presentacion as servicio
from app.servicios.ia_texto import ErrorIaTexto, analizar_inspiracion
from app.servicios.storage import StorageDep, extension_por_tipo

router = APIRouter(tags=["plantillas"])
registro = logging.getLogger("cotizador.plantillas")

Config = Annotated[Configuracion, Depends(obtener_configuracion)]


# ---------------------------------------------------------------------------
# Ayudantes
# ---------------------------------------------------------------------------

async def _leer_imagen(archivo: UploadFile) -> bytes:
    if archivo.content_type not in TIPOS_PERMITIDOS:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Sólo se aceptan PNG, JPG o WebP.")
    contenido = await archivo.read()
    if not contenido:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El archivo está vacío.")
    if len(contenido) > TAMANO_MAXIMO:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "La imagen supera 15 MB.")
    return contenido


async def _guardar_inspiracion(
    db: Any, storage: Any, archivo: UploadFile, contenido: bytes, usuario: Any
) -> dict[str, Any]:
    ruta = f"inspiraciones/{uuid4().hex}{extension_por_tipo(archivo.content_type, archivo.filename)}"
    await storage.subir(storage.bucket_imagenes, ruta, contenido, archivo.content_type or "image/jpeg")
    creada = (
        await db.table("imagenes")
        .insert(
            {
                "item_id": None,
                "ruta_storage": ruta,
                "tipo": "inspiracion",
                "etiquetas": ["inspiracion"],
                "origen": {"fuente": "inspiracion", "nombre_archivo": archivo.filename or ""},
                "subida_por": str(usuario.id),
            }
        )
        .execute()
    )
    return creada.data[0]


def _parametros_desde_ia(datos: dict[str, Any]) -> tuple[ParametrosPlantilla, str, str]:
    """Lo que devolvió la IA, filtrado a lo que el modelo acepta. Lo que venga raro usa el valor por defecto."""
    campos = set(ParametrosPlantilla.model_fields)
    limpios = {k: v for k, v in datos.items() if k in campos and v is not None}
    try:
        parametros = ParametrosPlantilla.model_validate(limpios)
    except Exception as error:  # la IA propuso algo fuera de rango
        registro.warning("Parámetros de la IA no válidos (%s); se usan los de por defecto.", error)
        parametros = ParametrosPlantilla()
    nombre = str(datos.get("nombre") or "").strip()[:60]
    descripcion = str(datos.get("descripcion") or "").strip()[:300]
    return parametros, nombre, descripcion


async def _armar_plantilla(storage: Any, fila: dict[str, Any], imagenes: dict[str, dict[str, Any]]) -> Plantilla:
    config = fila.get("config") or {}
    try:
        parametros = ParametrosPlantilla.model_validate(config.get("parametros") or {})
    except Exception:
        parametros = ParametrosPlantilla()
    crudas = [imagenes[i] for i in (config.get("inspiraciones") or []) if i in imagenes]
    return Plantilla(
        id=fila["id"],
        nombre=fila["nombre"],
        descripcion=fila.get("descripcion") or "",
        parametros=parametros,
        inspiraciones=await con_urls(storage, crudas),
        creado_en=fila.get("creado_en"),
    )


async def _armar_varias(db: Any, storage: Any, filas: list[dict[str, Any]]) -> list[Plantilla]:
    ids = {i for f in filas for i in ((f.get("config") or {}).get("inspiraciones") or [])}
    imagenes: dict[str, dict[str, Any]] = {}
    if ids:
        datos = (await db.table("imagenes").select("*").in_("id", sorted(ids)).execute()).data or []
        imagenes = {str(d["id"]): d for d in datos}
    return [await _armar_plantilla(storage, f, imagenes) for f in filas]


async def _fila_plantilla(db: Any, plantilla_id: UUID) -> dict[str, Any]:
    respuesta = await db.table("plantillas").select("*").eq("id", str(plantilla_id)).limit(1).execute()
    if not respuesta.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La plantilla no existe.")
    return respuesta.data[0]


def _puede_editar(fila: dict[str, Any], usuario: Any, que: str) -> None:
    if str(fila.get("creado_por")) != str(usuario.id) and not usuario.es_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Sólo quien creó {que} (o un admin) puede cambiarla.")


# ---------------------------------------------------------------------------
# Plantillas
# ---------------------------------------------------------------------------

@router.get("/plantillas", response_model=list[Plantilla])
async def listar_plantillas(usuario: Usuario, db: ClienteDB, storage: StorageDep) -> list[Plantilla]:
    """Plantillas del equipo, la más nueva primero."""
    respuesta = await db.table("plantillas").select("*").order("creado_en", desc=True).limit(100).execute()
    return await _armar_varias(db, storage, respuesta.data or [])


@router.post("/plantillas", response_model=Plantilla, status_code=status.HTTP_201_CREATED)
async def crear_plantilla(
    archivo: UploadFile,
    usuario: Usuario,
    db: ClienteDB,
    storage: StorageDep,
    config_app: Config,
    nombre: Annotated[str, Form()] = "",
) -> Plantilla:
    """Sube una inspiración y arma con ella una plantilla.

    La IA mira la imagen y propone los parámetros; si no está disponible, al menos se saca la paleta
    de la imagen y se avisa en la descripción.
    """
    contenido = await _leer_imagen(archivo)
    imagen = await _guardar_inspiracion(db, storage, archivo, contenido, usuario)

    try:
        propuesta = await analizar_inspiracion(contenido, config_app)
        parametros, nombre_ia, descripcion = _parametros_desde_ia(propuesta)
    except ErrorIaTexto as error:
        registro.warning("Sin IA para la inspiración (%s): se usa la paleta local.", error)
        parametros = ParametrosPlantilla(paleta=servicio.paleta_de_imagen(contenido))
        nombre_ia, descripcion = "", "Paleta tomada de la inspiración. La IA no estaba disponible para el resto."

    fila = (
        await db.table("plantillas")
        .insert(
            {
                "nombre": (nombre.strip() or nombre_ia or "Plantilla nueva")[:60],
                "descripcion": descripcion,
                "config": {"parametros": parametros.model_dump(mode="json"), "inspiraciones": [str(imagen["id"])]},
                "creado_por": str(usuario.id),
            }
        )
        .execute()
    ).data[0]
    return await _armar_plantilla(storage, fila, {str(imagen["id"]): imagen})


@router.patch("/plantillas/{plantilla_id}", response_model=Plantilla)
async def actualizar_plantilla(
    plantilla_id: UUID, cuerpo: PlantillaActualizacion, usuario: Usuario, db: ClienteDB, storage: StorageDep
) -> Plantilla:
    """Renombrar la plantilla o ajustar sus parámetros."""
    fila = await _fila_plantilla(db, plantilla_id)
    _puede_editar(fila, usuario, "la plantilla")
    cambios: dict[str, Any] = {}
    if cuerpo.nombre is not None:
        cambios["nombre"] = cuerpo.nombre.strip()[:60]
    if cuerpo.descripcion is not None:
        cambios["descripcion"] = cuerpo.descripcion.strip()[:300]
    if cuerpo.parametros is not None:
        config = dict(fila.get("config") or {})
        config["parametros"] = cuerpo.parametros.model_dump(mode="json")
        cambios["config"] = config
    if cambios:
        await db.table("plantillas").update(cambios).eq("id", str(plantilla_id)).execute()
    return (await _armar_varias(db, storage, [await _fila_plantilla(db, plantilla_id)]))[0]


@router.post("/plantillas/{plantilla_id}/inspiraciones", response_model=Plantilla)
async def agregar_inspiracion(
    plantilla_id: UUID, archivo: UploadFile, usuario: Usuario, db: ClienteDB, storage: StorageDep
) -> Plantilla:
    """Otra imagen de referencia para la misma plantilla (guía a la IA al generar los montajes)."""
    fila = await _fila_plantilla(db, plantilla_id)
    _puede_editar(fila, usuario, "la plantilla")
    contenido = await _leer_imagen(archivo)
    imagen = await _guardar_inspiracion(db, storage, archivo, contenido, usuario)

    config = dict(fila.get("config") or {})
    config["inspiraciones"] = [*(config.get("inspiraciones") or []), str(imagen["id"])]
    await db.table("plantillas").update({"config": config}).eq("id", str(plantilla_id)).execute()
    return (await _armar_varias(db, storage, [await _fila_plantilla(db, plantilla_id)]))[0]


@router.delete("/plantillas/{plantilla_id}/inspiraciones/{imagen_id}", response_model=Plantilla)
async def quitar_inspiracion(
    plantilla_id: UUID, imagen_id: UUID, usuario: Usuario, db: ClienteDB, storage: StorageDep
) -> Plantilla:
    fila = await _fila_plantilla(db, plantilla_id)
    _puede_editar(fila, usuario, "la plantilla")
    config = dict(fila.get("config") or {})
    config["inspiraciones"] = [i for i in (config.get("inspiraciones") or []) if i != str(imagen_id)]
    await db.table("plantillas").update({"config": config}).eq("id", str(plantilla_id)).execute()
    await _borrar_inspiracion(db, storage, imagen_id)
    return (await _armar_varias(db, storage, [await _fila_plantilla(db, plantilla_id)]))[0]


async def _borrar_inspiracion(db: Any, storage: Any, imagen_id: UUID) -> None:
    """Borra la imagen de inspiración si ya no la usa ninguna plantilla."""
    fila = (await db.table("imagenes").select("*").eq("id", str(imagen_id)).limit(1).execute()).data
    if not fila or fila[0].get("tipo") != "inspiracion":
        return
    # Se revisa en Python: filtrar dentro de un arreglo jsonb desde PostgREST es más frágil que leer
    # las plantillas (son pocas) y buscar el id.
    plantillas = (await db.table("plantillas").select("config").execute()).data or []
    if any(str(imagen_id) in ((p.get("config") or {}).get("inspiraciones") or []) for p in plantillas):
        return
    try:
        await storage.eliminar(storage.bucket_imagenes, fila[0]["ruta_storage"])
    except HTTPException as error:
        registro.warning("No se pudo borrar la inspiración %s de Storage: %s", imagen_id, error.detail)
    await db.table("imagenes").delete().eq("id", str(imagen_id)).execute()


@router.post("/plantillas/{plantilla_id}/analizar", response_model=Plantilla)
async def analizar_plantilla(
    plantilla_id: UUID, usuario: Usuario, db: ClienteDB, storage: StorageDep, config_app: Config
) -> Plantilla:
    """Vuelve a mirar la primera inspiración y propone los parámetros otra vez."""
    fila = await _fila_plantilla(db, plantilla_id)
    _puede_editar(fila, usuario, "la plantilla")
    config = dict(fila.get("config") or {})
    ids = config.get("inspiraciones") or []
    if not ids:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "La plantilla no tiene ninguna inspiración que mirar.")

    imagen = (await db.table("imagenes").select("*").eq("id", ids[0]).limit(1).execute()).data
    if not imagen:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La imagen de inspiración ya no existe.")
    contenido = await storage.descargar(storage.bucket_imagenes, imagen[0]["ruta_storage"])

    try:
        propuesta = await analizar_inspiracion(contenido, config_app)
    except ErrorIaTexto as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(error)) from error
    parametros, nombre_ia, descripcion = _parametros_desde_ia(propuesta)

    config["parametros"] = parametros.model_dump(mode="json")
    cambios: dict[str, Any] = {"config": config}
    if descripcion:
        cambios["descripcion"] = descripcion
    if nombre_ia and not (fila.get("nombre") or "").strip():
        cambios["nombre"] = nombre_ia
    await db.table("plantillas").update(cambios).eq("id", str(plantilla_id)).execute()
    return (await _armar_varias(db, storage, [await _fila_plantilla(db, plantilla_id)]))[0]


@router.delete("/plantillas/{plantilla_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_plantilla(plantilla_id: UUID, usuario: Usuario, db: ClienteDB, storage: StorageDep) -> None:
    """Borra la plantilla y sus inspiraciones. Las presentaciones ya armadas no cambian: tienen copia
    de los parámetros."""
    fila = await _fila_plantilla(db, plantilla_id)
    _puede_editar(fila, usuario, "la plantilla")
    await db.table("plantillas").delete().eq("id", str(plantilla_id)).execute()
    for imagen_id in (fila.get("config") or {}).get("inspiraciones") or []:
        await _borrar_inspiracion(db, storage, UUID(imagen_id))


# ---------------------------------------------------------------------------
# Paletas
# ---------------------------------------------------------------------------

@router.get("/paletas", response_model=list[PaletaGuardada])
async def listar_paletas(usuario: Usuario, db: ClienteDB) -> list[PaletaGuardada]:
    """Las que trae la app y las que guardó el equipo."""
    respuesta = await db.table("paletas").select("*").order("creado_en", desc=True).limit(100).execute()
    guardadas = [
        PaletaGuardada(
            id=f["id"],
            nombre=f["nombre"],
            paleta={"fondo": f["fondo"], "texto": f["texto"], "acento": f["acento"]},
        )
        for f in respuesta.data or []
    ]
    return servicio.paletas_predefinidas() + guardadas


@router.post("/paletas", response_model=PaletaGuardada, status_code=status.HTTP_201_CREATED)
async def crear_paleta(cuerpo: PaletaEntrada, usuario: Usuario, db: ClienteDB) -> PaletaGuardada:
    fila = (
        await db.table("paletas")
        .insert(
            {
                "nombre": cuerpo.nombre.strip(),
                "fondo": cuerpo.paleta.fondo,
                "texto": cuerpo.paleta.texto,
                "acento": cuerpo.paleta.acento,
                "creado_por": str(usuario.id),
            }
        )
        .execute()
    ).data[0]
    return PaletaGuardada(id=fila["id"], nombre=fila["nombre"], paleta=cuerpo.paleta)


@router.patch("/paletas/{paleta_id}", response_model=PaletaGuardada)
async def actualizar_paleta(paleta_id: UUID, cuerpo: PaletaEntrada, usuario: Usuario, db: ClienteDB) -> PaletaGuardada:
    fila = (await db.table("paletas").select("*").eq("id", str(paleta_id)).limit(1).execute()).data
    if not fila:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La paleta no existe.")
    _puede_editar(fila[0], usuario, "la paleta")
    await (
        db.table("paletas")
        .update(
            {
                "nombre": cuerpo.nombre.strip(),
                "fondo": cuerpo.paleta.fondo,
                "texto": cuerpo.paleta.texto,
                "acento": cuerpo.paleta.acento,
            }
        )
        .eq("id", str(paleta_id))
        .execute()
    )
    return PaletaGuardada(id=paleta_id, nombre=cuerpo.nombre.strip(), paleta=cuerpo.paleta)


@router.delete("/paletas/{paleta_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_paleta(paleta_id: UUID, usuario: Usuario, db: ClienteDB) -> None:
    fila = (await db.table("paletas").select("*").eq("id", str(paleta_id)).limit(1).execute()).data
    if not fila:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La paleta no existe.")
    _puede_editar(fila[0], usuario, "la paleta")
    await db.table("paletas").delete().eq("id", str(paleta_id)).execute()


# Las plantillas exponen sus inspiraciones con URL firmada como cualquier otra imagen.
__all__ = ["router", "Imagen"]
