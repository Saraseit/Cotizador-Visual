"""Imágenes: subir a la biblioteca y generar variantes con IA."""

from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status

from app.auth import Usuario
from app.config import Configuracion, obtener_configuracion
from app.db.cliente import ClienteDB
from app.db.modelos import Imagen, PeticionGenerarImagen, ResultadoGeneracion
from app.routers.catalogo import con_urls
from app.servicios.proveedor_imagenes import ErrorProveedorImagenes, obtener_proveedor
from app.servicios.storage import StorageDep, extension_por_tipo

router = APIRouter(prefix="/imagenes", tags=["imagenes"])

Config = Annotated[Configuracion, Depends(obtener_configuracion)]

TIPOS_PERMITIDOS = {"image/png", "image/jpeg", "image/webp"}
TAMANO_MAXIMO = 15 * 1024 * 1024


def _etiquetas_desde_texto(texto: str | None) -> list[str]:
    if not texto:
        return []
    return sorted({e.strip().lower() for e in texto.split(",") if e.strip()})


async def _codigo_del_item(db: Any, item_id: UUID | None) -> str | None:
    if item_id is None:
        return None
    respuesta = await db.table("catalogo_items").select("codigo").eq("id", str(item_id)).limit(1).execute()
    if not respuesta.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El ítem del catálogo no existe.")
    return str(respuesta.data[0]["codigo"])


def _ruta_imagen(codigo: str | None, extension: str, subcarpeta: str = "") -> str:
    base = f"catalogo/{codigo}" if codigo else "ad_hoc"
    if subcarpeta:
        base = f"{base}/{subcarpeta}"
    return f"{base}/{uuid4().hex}{extension}"


@router.post("", response_model=Imagen, status_code=status.HTTP_201_CREATED)
async def subir_imagen(
    archivo: UploadFile,
    usuario: Usuario,
    db: ClienteDB,
    storage: StorageDep,
    item_id: Annotated[UUID | None, Form()] = None,
    etiquetas: Annotated[str | None, Form(description="Separadas por coma")] = None,
    tipo: Annotated[str, Form()] = "variante",
) -> Imagen:
    """Sube una imagen a la biblioteca. Sin `item_id` queda como imagen ad hoc."""
    if archivo.content_type not in TIPOS_PERMITIDOS:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Sólo se aceptan PNG, JPG o WebP.")
    if tipo not in {"oficial", "variante"}:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "tipo debe ser 'oficial' o 'variante'.")
    contenido = await archivo.read()
    if not contenido:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El archivo está vacío.")
    if len(contenido) > TAMANO_MAXIMO:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "La imagen supera 15 MB.")

    codigo = await _codigo_del_item(db, item_id)
    if tipo == "oficial":
        if item_id is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Una imagen oficial necesita item_id.")
        existente = await db.table("imagenes").select("id").eq("item_id", str(item_id)).eq("tipo", "oficial").limit(1).execute()
        if existente.data:
            raise HTTPException(status.HTTP_409_CONFLICT, "El ítem ya tiene imagen oficial; sube una variante.")

    ruta = _ruta_imagen(codigo, extension_por_tipo(archivo.content_type, archivo.filename))
    await storage.subir(storage.bucket_imagenes, ruta, contenido, archivo.content_type or "image/png")

    fila = {
        "item_id": str(item_id) if item_id else None,
        "ruta_storage": ruta,
        "tipo": tipo,
        "etiquetas": _etiquetas_desde_texto(etiquetas),
        "origen": {"nombre_archivo": archivo.filename or ""},
        "subida_por": str(usuario.id),
    }
    creada = await db.table("imagenes").insert(fila).execute()
    return (await con_urls(storage, creada.data))[0]


@router.post("/generar", response_model=ResultadoGeneracion)
async def generar_imagenes(
    cuerpo: PeticionGenerarImagen, usuario: Usuario, db: ClienteDB, storage: StorageDep, config: Config
) -> ResultadoGeneracion:
    """Genera variantes a partir de una imagen base. Sin item_id (ítems ad hoc) quedan como imágenes sueltas."""
    base = await db.table("imagenes").select("*").eq("id", str(cuerpo.imagen_base_id)).limit(1).execute()
    if not base.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La imagen base no existe.")
    imagen_base = base.data[0]
    item_id = cuerpo.item_id or (UUID(imagen_base["item_id"]) if imagen_base.get("item_id") else None)
    if cuerpo.item_id and imagen_base.get("item_id") and str(imagen_base["item_id"]) != str(cuerpo.item_id):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "La imagen base no pertenece al ítem indicado.")
    codigo = await _codigo_del_item(db, item_id)

    try:
        proveedor = obtener_proveedor(config)
    except ErrorProveedorImagenes as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(error)) from error

    bytes_base = await storage.descargar(storage.bucket_imagenes, imagen_base["ruta_storage"])
    try:
        variantes = await proveedor.generar_variantes(bytes_base, cuerpo.peticion, config.variantes_por_generacion)
    except ErrorProveedorImagenes as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(error)) from error

    filas = []
    for datos in variantes:
        ruta = _ruta_imagen(codigo, ".png", subcarpeta="generadas")
        await storage.subir(storage.bucket_imagenes, ruta, datos, "image/png")
        filas.append(
            {
                "item_id": str(item_id) if item_id else None,
                "ruta_storage": ruta,
                "tipo": "generada",
                "etiquetas": ["render conceptual"],
                "origen": {
                    "peticion": cuerpo.peticion,
                    "imagen_base_id": str(cuerpo.imagen_base_id),
                    "proveedor": proveedor.nombre,
                    "modelo": proveedor.modelo,
                },
                "subida_por": str(usuario.id),
            }
        )
    creadas = await db.table("imagenes").insert(filas).execute()
    return ResultadoGeneracion(imagenes=await con_urls(storage, creadas.data or []))
