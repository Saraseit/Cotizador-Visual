"""Catálogo: ítems (alta por formulario o por texto), listas de precios e imágenes por ítem."""

import re
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.auth import Usuario
from app.db.cliente import ClienteDB
from app.db.modelos import (
    CargaTexto,
    CatalogoItem,
    CatalogoItemActualizacion,
    CatalogoItemEntrada,
    Imagen,
    ListaPrecios,
    ListaPreciosEntrada,
    PrecioItem,
    ResultadoCargaTexto,
)
from app.servicios.catalogo_texto import parsear_texto_catalogo
from app.servicios.matching import normalizar_codigo
from app.servicios.storage import StorageDep

router = APIRouter(prefix="/catalogo", tags=["catalogo"])

_ORDEN_TIPO = {"oficial": 0, "variante": 1, "generada": 2}
SELECT_ITEM = "*, precios:precios_items(lista_id, precio, lista:listas_precios(nombre)), imagenes(*)"
CAMPOS_ITEM = ("codigo", "nombre", "categoria", "descripcion", "medidas", "etiquetas", "costo_reposicion", "activo")


# ---------------------------------------------------------------------------
# Ayudantes
# ---------------------------------------------------------------------------

def ordenar_imagenes(imagenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Oficial primero; después por usos (desc) y fecha (más reciente primero)."""
    return sorted(
        imagenes,
        key=lambda i: (_ORDEN_TIPO.get(i.get("tipo", ""), 9), -int(i.get("usos") or 0), str(i.get("creado_en", ""))),
    )


async def con_urls(storage: Any, imagenes: list[dict[str, Any]]) -> list[Imagen]:
    urls = await storage.urls_firmadas(storage.bucket_imagenes, [i["ruta_storage"] for i in imagenes])
    return [Imagen(**i, url=urls.get(i["ruta_storage"])) for i in imagenes]


async def armar_items(storage: Any, filas: list[dict[str, Any]]) -> list[CatalogoItem]:
    """Convierte filas con `precios` e `imagenes` embebidos en CatalogoItem con URL de la oficial."""
    oficiales: dict[str, dict[str, Any]] = {}
    for fila in filas:
        oficial = next((i for i in fila.get("imagenes") or [] if i.get("tipo") == "oficial"), None)
        if oficial:
            oficiales[str(fila["id"])] = oficial
    urls = await storage.urls_firmadas(storage.bucket_imagenes, [o["ruta_storage"] for o in oficiales.values()])

    items: list[CatalogoItem] = []
    for fila in filas:
        datos = {k: v for k, v in fila.items() if k not in ("precios", "imagenes")}
        precios = [
            PrecioItem(lista_id=p["lista_id"], precio=float(p["precio"] or 0), nombre_lista=(p.get("lista") or {}).get("nombre"))
            for p in fila.get("precios") or []
        ]
        oficial = oficiales.get(str(fila["id"]))
        items.append(
            CatalogoItem(
                **datos,
                precios=sorted(precios, key=lambda p: p.nombre_lista or ""),
                imagen_oficial=Imagen(**oficial, url=urls.get(oficial["ruta_storage"])) if oficial else None,
                total_imagenes=len(fila.get("imagenes") or []),
            )
        )
    return items


async def _cargar_item(db: Any, storage: Any, item_id: UUID) -> CatalogoItem:
    respuesta = await db.table("catalogo_items").select(SELECT_ITEM).eq("id", str(item_id)).limit(1).execute()
    if not respuesta.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El ítem no existe.")
    return (await armar_items(storage, respuesta.data))[0]


async def _guardar_precios(db: Any, item_id: str, precios: dict[UUID, float]) -> None:
    """Deja exactamente los precios indicados: upsert de los presentes y borrado del resto."""
    if precios:
        filas = [{"item_id": item_id, "lista_id": str(lista), "precio": float(precio)} for lista, precio in precios.items()]
        await db.table("precios_items").upsert(filas, on_conflict="item_id,lista_id").execute()
    consulta = db.table("precios_items").delete().eq("item_id", item_id)
    if precios:
        consulta = consulta.not_.in_("lista_id", [str(l) for l in precios])
    await consulta.execute()


def _limpiar_etiquetas(etiquetas: list[str] | None) -> list[str]:
    return sorted({e.strip().lower() for e in etiquetas or [] if e.strip()})


# ---------------------------------------------------------------------------
# Listas de precios
# ---------------------------------------------------------------------------

@router.get("/listas-precios", response_model=list[ListaPrecios])
async def listar_listas_precios(usuario: Usuario, db: ClienteDB) -> list[ListaPrecios]:
    respuesta = await db.table("listas_precios").select("*").order("orden").order("nombre").execute()
    return [ListaPrecios(**f) for f in respuesta.data or []]


@router.post("/listas-precios", response_model=ListaPrecios, status_code=status.HTTP_201_CREATED)
async def crear_lista_precios(cuerpo: ListaPreciosEntrada, usuario: Usuario, db: ClienteDB) -> ListaPrecios:
    existe = await db.table("listas_precios").select("id").ilike("nombre", cuerpo.nombre.strip()).limit(1).execute()
    if existe.data:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una lista con ese nombre.")
    fila = {"nombre": cuerpo.nombre.strip(), "orden": cuerpo.orden or 0, "activo": cuerpo.activo if cuerpo.activo is not None else True}
    creada = await db.table("listas_precios").insert(fila).execute()
    return ListaPrecios(**creada.data[0])


@router.patch("/listas-precios/{lista_id}", response_model=ListaPrecios)
async def actualizar_lista_precios(lista_id: UUID, cuerpo: ListaPreciosEntrada, usuario: Usuario, db: ClienteDB) -> ListaPrecios:
    cambios = {k: v for k, v in cuerpo.model_dump().items() if v is not None}
    if "nombre" in cambios:
        cambios["nombre"] = cambios["nombre"].strip()
    actualizada = await db.table("listas_precios").update(cambios).eq("id", str(lista_id)).execute()
    if not actualizada.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La lista no existe.")
    return ListaPrecios(**actualizada.data[0])


# ---------------------------------------------------------------------------
# Ítems
# ---------------------------------------------------------------------------

@router.get("/items", response_model=list[CatalogoItem])
async def buscar_items(
    usuario: Usuario,
    db: ClienteDB,
    storage: StorageDep,
    buscar: str = Query("", max_length=80),
    solo_activos: bool = False,
    limite: int = Query(100, le=500),
) -> list[CatalogoItem]:
    """Búsqueda por código, nombre o categoría (sin distinguir mayúsculas)."""
    consulta = db.table("catalogo_items").select(SELECT_ITEM).order("codigo").limit(limite)
    termino = re.sub(r"[,()%*]", " ", buscar).strip()
    if termino:
        consulta = consulta.or_(f"codigo.ilike.*{termino}*,nombre.ilike.*{termino}*,categoria.ilike.*{termino}*")
    if solo_activos:
        consulta = consulta.eq("activo", True)
    respuesta = await consulta.execute()
    return await armar_items(storage, respuesta.data or [])


@router.post("/items", response_model=CatalogoItem, status_code=status.HTTP_201_CREATED)
async def crear_item(cuerpo: CatalogoItemEntrada, usuario: Usuario, db: ClienteDB, storage: StorageDep) -> CatalogoItem:
    codigo = normalizar_codigo(cuerpo.codigo)
    if not codigo:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "El código no puede estar vacío.")
    existe = await db.table("catalogo_items").select("id").eq("codigo", codigo).limit(1).execute()
    if existe.data:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Ya existe un ítem con el código {codigo}.")

    fila = cuerpo.model_dump(exclude={"precios"})
    fila["codigo"] = codigo
    fila["etiquetas"] = _limpiar_etiquetas(cuerpo.etiquetas)
    creado = await db.table("catalogo_items").insert(fila).execute()
    item_id = creado.data[0]["id"]
    await _guardar_precios(db, item_id, cuerpo.precios)
    return await _cargar_item(db, storage, UUID(item_id))


@router.post("/items/carga-texto", response_model=ResultadoCargaTexto)
async def cargar_items_por_texto(cuerpo: CargaTexto, usuario: Usuario, db: ClienteDB, storage: StorageDep) -> ResultadoCargaTexto:
    """Alta rápida: pega líneas `codigo; nombre; categoria; ...`. Hace upsert por código."""
    filas, errores = parsear_texto_catalogo(cuerpo.texto)
    if not filas:
        return ResultadoCargaTexto(errores=errores or ["No se encontró ninguna línea válida."])

    codigos = [f["codigo"] for f in filas]
    existentes = await db.table("catalogo_items").select("*").in_("codigo", codigos).execute()
    por_codigo = {normalizar_codigo(f["codigo"]): f for f in existentes.data or []}
    ya_existian = set(por_codigo)

    # PostgREST exige que todas las filas del upsert tengan las mismas claves. Además, un campo
    # vacío en el texto no debe borrar lo que el ítem ya tenía: se parte del registro existente.
    completas = []
    for fila in filas:
        base = por_codigo.get(fila["codigo"], {})
        completa = {
            "codigo": fila["codigo"],
            "nombre": fila.get("nombre") or base.get("nombre") or fila["codigo"],
            "categoria": fila.get("categoria") or base.get("categoria") or "",
            "descripcion": fila.get("descripcion") or base.get("descripcion") or "",
            "medidas": fila.get("medidas") or base.get("medidas") or "",
            "etiquetas": fila.get("etiquetas") or base.get("etiquetas") or [],
            "costo_reposicion": fila.get("costo_reposicion", base.get("costo_reposicion")),
            "activo": True,
        }
        completas.append(completa)

    guardados = await db.table("catalogo_items").upsert(completas, on_conflict="codigo").execute()
    ids = [f["id"] for f in guardados.data or []]
    completos = await db.table("catalogo_items").select(SELECT_ITEM).in_("id", ids).order("codigo").execute()
    items = await armar_items(storage, completos.data or [])
    return ResultadoCargaTexto(
        creados=sum(1 for c in codigos if c not in ya_existian),
        actualizados=sum(1 for c in codigos if c in ya_existian),
        errores=errores,
        items=items,
    )


@router.get("/items/{item_id}", response_model=CatalogoItem)
async def obtener_item(item_id: UUID, usuario: Usuario, db: ClienteDB, storage: StorageDep) -> CatalogoItem:
    return await _cargar_item(db, storage, item_id)


@router.patch("/items/{item_id}", response_model=CatalogoItem)
async def actualizar_item(
    item_id: UUID, cuerpo: CatalogoItemActualizacion, usuario: Usuario, db: ClienteDB, storage: StorageDep
) -> CatalogoItem:
    cambios = {k: v for k, v in cuerpo.model_dump(exclude={"precios"}).items() if v is not None}
    if "codigo" in cambios:
        codigo = normalizar_codigo(cambios["codigo"])
        if not codigo:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "El código no puede estar vacío.")
        duplicado = await db.table("catalogo_items").select("id").eq("codigo", codigo).neq("id", str(item_id)).limit(1).execute()
        if duplicado.data:
            raise HTTPException(status.HTTP_409_CONFLICT, f"Ya existe otro ítem con el código {codigo}.")
        cambios["codigo"] = codigo
    if "etiquetas" in cambios:
        cambios["etiquetas"] = _limpiar_etiquetas(cambios["etiquetas"])
    if cuerpo.costo_reposicion is None and "costo_reposicion" in cuerpo.model_fields_set:
        cambios["costo_reposicion"] = None  # permitir borrar el costo explícitamente

    if cambios:
        actualizado = await db.table("catalogo_items").update(cambios).eq("id", str(item_id)).execute()
        if not actualizado.data:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "El ítem no existe.")
    if cuerpo.precios is not None:
        await _guardar_precios(db, str(item_id), cuerpo.precios)
    return await _cargar_item(db, storage, item_id)


@router.get("/items/{item_id}/imagenes", response_model=list[Imagen])
async def imagenes_del_item(item_id: UUID, usuario: Usuario, db: ClienteDB, storage: StorageDep) -> list[Imagen]:
    item = await db.table("catalogo_items").select("id").eq("id", str(item_id)).limit(1).execute()
    if not item.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El ítem no existe.")
    respuesta = await db.table("imagenes").select("*").eq("item_id", str(item_id)).execute()
    return await con_urls(storage, ordenar_imagenes(respuesta.data or []))
