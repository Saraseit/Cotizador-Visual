"""Formato del PDF de la propuesta base: título, logotipo, imagen al pie, notas y campos extra.

Cualquiera lo puede ver; sólo un admin lo cambia, porque aplica a todas las propuestas del equipo.
"""

from uuid import uuid4

from fastapi import APIRouter, HTTPException, UploadFile, status

from app.auth import Usuario, UsuarioActual
from app.db.cliente import ClienteDB
from app.db.modelos import (
    AjustesPropuesta,
    AjustesPropuestaEntrada,
    AjustesPropuestaVista,
    HuecoMarca,
)
from app.servicios import ajustes_propuesta as servicio
from app.servicios.storage import StorageDep, extension_por_tipo

router = APIRouter(prefix="/ajustes", tags=["ajustes"])

TIPOS_PERMITIDOS = {"image/png", "image/jpeg", "image/webp"}
TAMANO_MAXIMO = 8 * 1024 * 1024


def _exigir_admin(usuario: UsuarioActual) -> None:
    if not usuario.es_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sólo un administrador puede cambiar el formato del PDF.")


async def _vista(storage: StorageDep, ajustes: AjustesPropuesta) -> AjustesPropuestaVista:
    rutas = [r for r in (ajustes.logotipo_ruta, ajustes.pie_ruta) if r]
    urls = await storage.urls_firmadas(storage.bucket_imagenes, rutas) if rutas else {}
    return AjustesPropuestaVista(
        **ajustes.model_dump(),
        logotipo_url=urls.get(ajustes.logotipo_ruta or ""),
        pie_url=urls.get(ajustes.pie_ruta or ""),
        logotipo_de_marca=not ajustes.logotipo_ruta,
    )


async def _borrar_archivo(storage: StorageDep, ruta: str | None) -> None:
    if not ruta:
        return
    try:
        await storage.eliminar(storage.bucket_imagenes, ruta)
    except HTTPException:
        pass  # ya no estaba: no importa


@router.get("/propuesta", response_model=AjustesPropuestaVista)
async def obtener(usuario: Usuario, db: ClienteDB, storage: StorageDep) -> AjustesPropuestaVista:
    return await _vista(storage, await servicio.leer(db))


@router.put("/propuesta", response_model=AjustesPropuestaVista)
async def guardar(cuerpo: AjustesPropuestaEntrada, usuario: Usuario, db: ClienteDB, storage: StorageDep) -> AjustesPropuestaVista:
    """Guarda textos y campos. Las imágenes se suben aparte y aquí se conservan."""
    _exigir_admin(usuario)
    anterior = await servicio.leer(db)
    nuevos = AjustesPropuesta(**cuerpo.model_dump(), logotipo_ruta=anterior.logotipo_ruta, pie_ruta=anterior.pie_ruta)
    await servicio.guardar(db, nuevos, str(usuario.id))
    return await _vista(storage, nuevos)


@router.post("/propuesta/imagenes/{hueco}", response_model=AjustesPropuestaVista)
async def subir_imagen(
    hueco: HuecoMarca, archivo: UploadFile, usuario: Usuario, db: ClienteDB, storage: StorageDep
) -> AjustesPropuestaVista:
    """Sube el logotipo (encabezado) o la imagen al pie (al final del documento). Reemplaza la anterior."""
    _exigir_admin(usuario)
    if archivo.content_type not in TIPOS_PERMITIDOS:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Sólo se aceptan PNG, JPG o WebP.")
    contenido = await archivo.read()
    if not contenido:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El archivo está vacío.")
    if len(contenido) > TAMANO_MAXIMO:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "La imagen supera 8 MB.")
    try:
        servicio.a_data_uri(contenido, 64)  # que se pueda abrir antes de guardarla
    except Exception as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "No se pudo leer la imagen.") from error

    ruta = f"marca/propuesta/{hueco}-{uuid4().hex}{extension_por_tipo(archivo.content_type, archivo.filename)}"
    await storage.subir(storage.bucket_imagenes, ruta, contenido, archivo.content_type or "image/png")
    ajustes = await servicio.leer(db)
    anterior = ajustes.logotipo_ruta if hueco == "logotipo" else ajustes.pie_ruta
    if hueco == "logotipo":
        ajustes.logotipo_ruta = ruta
    else:
        ajustes.pie_ruta = ruta
    await servicio.guardar(db, ajustes, str(usuario.id))
    await _borrar_archivo(storage, anterior)
    return await _vista(storage, ajustes)


@router.delete("/propuesta/imagenes/{hueco}", response_model=AjustesPropuestaVista)
async def quitar_imagen(hueco: HuecoMarca, usuario: Usuario, db: ClienteDB, storage: StorageDep) -> AjustesPropuestaVista:
    """Sin logotipo subido vuelve el de la marca; sin imagen al pie, el PDF termina en las notas."""
    _exigir_admin(usuario)
    ajustes = await servicio.leer(db)
    anterior = ajustes.logotipo_ruta if hueco == "logotipo" else ajustes.pie_ruta
    if hueco == "logotipo":
        ajustes.logotipo_ruta = None
    else:
        ajustes.pie_ruta = None
    await servicio.guardar(db, ajustes, str(usuario.id))
    await _borrar_archivo(storage, anterior)
    return await _vista(storage, ajustes)
