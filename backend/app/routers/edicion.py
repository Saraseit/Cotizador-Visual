"""Edición de la cotización en Revisar: cambios negociados después del PDF del sistema.

Siempre se parte de una cotización del sistema principal; aquí se agregan o quitan partidas, se cambian
cantidades, precios y secciones. Todo queda en el historial de cambios y la cotización se marca como
"no alineada al sistema principal" hasta que el vendedor indica que ya aplicó los cambios allá. Nada de
esto bloquea generar los PDF.
"""

import re
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.auth import Usuario
from app.db.cliente import ClienteDB
from app.db.modelos import (
    CambioHistorial,
    CotizacionDetalle,
    EditarPartida,
    NuevaPartida,
    RenombrarSeccion,
)
from app.routers.cotizaciones import _fila_cotizacion, _puede_editar, cargar_detalle
from app.servicios.cargos import clasificar_cargo
from app.servicios.matching import elegir_imagen_sugerida, normalizar_codigo
from app.servicios.render_pdf import formatear_cantidad, formatear_moneda
from app.servicios.storage import StorageDep

router = APIRouter(prefix="/cotizaciones", tags=["edicion"])


# ---------------------------------------------------------------------------
# Ayudantes
# ---------------------------------------------------------------------------

async def _editable(db: Any, cotizacion_id: UUID, usuario: Any) -> dict[str, Any]:
    cotizacion = await _fila_cotizacion(db, cotizacion_id, "*")
    _puede_editar(cotizacion, usuario)
    return cotizacion


async def _partidas(db: Any, cotizacion_id: UUID) -> list[dict[str, Any]]:
    respuesta = (
        await db.table("cotizacion_items")
        .select("id, orden, categoria, eliminada, compuesto_id, creado_en")
        .eq("cotizacion_id", str(cotizacion_id))
        .execute()
    )
    return sorted(respuesta.data or [], key=lambda f: (f.get("orden") or 0, f.get("creado_en") or ""))


async def _partida(db: Any, cotizacion_id: UUID, item_id: UUID) -> dict[str, Any]:
    respuesta = (
        await db.table("cotizacion_items")
        .select("*")
        .eq("id", str(item_id))
        .eq("cotizacion_id", str(cotizacion_id))
        .limit(1)
        .execute()
    )
    if not respuesta.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La partida no pertenece a esta cotización.")
    return respuesta.data[0]


async def registrar(db: Any, cotizacion_id: UUID, usuario: Any, tipo: str, descripcion: str, **datos: Any) -> None:
    await db.table("cotizacion_cambios").insert(
        {
            "cotizacion_id": str(cotizacion_id),
            "usuario_id": str(usuario.id),
            "tipo": tipo,
            "descripcion": descripcion,
            "datos": {k: (str(v) if isinstance(v, UUID) else v) for k, v in datos.items()},
        }
    ).execute()


def seccion_normalizada(nombre: str, existentes: list[str]) -> str:
    """Sin espacios de más; si ya existe una sección igual (sin importar mayúsculas), se usa esa."""
    limpio = re.sub(r"\s+", " ", nombre or "").strip()
    return next((e for e in existentes if e.lower() == limpio.lower()), limpio)


def orden_tras_seccion(filas: list[dict[str, Any]], mover: list[str], destino: str) -> list[str] | None:
    """Nuevo orden con las partidas `mover` justo después de la última de la sección `destino`.

    Así una partida que cambia de sección no abre un segundo bloque con el mismo título. None si la
    sección destino no tiene otras partidas (la partida se queda donde está y abre la sección ahí).
    """
    resto = [f for f in filas if str(f["id"]) not in mover]
    ultimas = [i for i, f in enumerate(resto) if not f.get("eliminada") and (f.get("categoria") or "") == destino]
    if not ultimas:
        return None
    movidas = [f for f in filas if str(f["id"]) in mover]
    nuevo = resto[: ultimas[-1] + 1] + movidas + resto[ultimas[-1] + 1 :]
    return [str(f["id"]) for f in nuevo]


async def _reordenar(db: Any, cotizacion_id: UUID, ids: list[str] | None) -> None:
    if ids:
        await db.rpc("reordenar_cotizacion", {"p_cotizacion": str(cotizacion_id), "p_ids": ids}).execute()


async def _limpiar_compuesto(db: Any, compuesto_id: Any) -> None:
    """Un compuesto con menos de dos partidas vigentes deja de tener sentido: se separa."""
    if not compuesto_id:
        return
    vigentes = (
        await db.table("cotizacion_items").select("id").eq("compuesto_id", str(compuesto_id)).eq("eliminada", False).execute()
    ).data or []
    if len(vigentes) < 2:
        await db.table("cotizacion_items").update({"compuesto_id": None}).eq("compuesto_id", str(compuesto_id)).execute()
        await db.table("cotizacion_compuestos").delete().eq("id", str(compuesto_id)).execute()


def _nombre(fila: dict[str, Any]) -> str:
    texto = (fila.get("descripcion_editada") or "").strip() or fila.get("descripcion_origen") or ""
    return texto[:80]


def _seccion(nombre: str) -> str:
    return nombre or "sin sección"


async def _renombrar_en_presentacion(db: Any, cotizacion_id: UUID, de: str, a: str) -> None:
    """La presentación editorial guarda ajustes por sección (título, texto, montaje): se mudan al nombre nuevo."""
    respuesta = await db.table("presentaciones").select("config").eq("cotizacion_id", str(cotizacion_id)).limit(1).execute()
    if not respuesta.data or not respuesta.data[0].get("config"):
        return
    config = dict(respuesta.data[0]["config"])
    secciones = list(config.get("secciones") or [])
    if any(s.get("clave") == a for s in secciones):
        secciones = [s for s in secciones if s.get("clave") != de]
    else:
        for s in secciones:
            if s.get("clave") == de:
                s["clave"] = a
                if (s.get("titulo") or "").strip().upper() == (de or "MOBILIARIO").strip().upper()[:40]:
                    s["titulo"] = (a or "MOBILIARIO").strip().upper()[:40]
    imagenes = dict(config.get("imagenes") or {})
    if f"montaje:{de}" in imagenes and f"montaje:{a}" not in imagenes:
        imagenes[f"montaje:{a}"] = imagenes.pop(f"montaje:{de}")
    config.update(secciones=secciones, imagenes=imagenes)
    await db.table("presentaciones").update({"config": config}).eq("cotizacion_id", str(cotizacion_id)).execute()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/{cotizacion_id}/partidas", response_model=CotizacionDetalle, status_code=status.HTTP_201_CREATED)
async def agregar_partida(
    cotizacion_id: UUID, cuerpo: NuevaPartida, usuario: Usuario, db: ClienteDB, storage: StorageDep
) -> CotizacionDetalle:
    """Agrega una partida que no viene en el PDF del sistema (del catálogo o fuera de él)."""
    await _editable(db, cotizacion_id, usuario)
    filas = await _partidas(db, cotizacion_id)
    categoria = seccion_normalizada(cuerpo.categoria, [f.get("categoria") or "" for f in filas if not f.get("eliminada")])

    item: dict[str, Any] | None = None
    if cuerpo.item_id:
        respuesta = await db.table("catalogo_items").select("*").eq("id", str(cuerpo.item_id)).limit(1).execute()
        if not respuesta.data:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "El artículo del catálogo no existe.")
        item = respuesta.data[0]
    elif cuerpo.codigo.strip():
        respuesta = await db.table("catalogo_items").select("*").eq("codigo", normalizar_codigo(cuerpo.codigo)).limit(1).execute()
        item = (respuesta.data or [None])[0]
    imagen_id = None
    if item:
        imagenes = (
            await db.table("imagenes").select("*").eq("item_id", str(item["id"])).in_("tipo", ["oficial", "variante"]).execute()
        ).data or []
        sugerida = elegir_imagen_sugerida(imagenes)
        imagen_id = sugerida["id"] if sugerida else None

    creada = (
        await db.table("cotizacion_items")
        .insert(
            {
                "cotizacion_id": str(cotizacion_id),
                "item_id": str(item["id"]) if item else None,
                "codigo_origen": (item["codigo"] if item else cuerpo.codigo.strip())[:40],
                "descripcion_origen": cuerpo.descripcion.strip(),
                "cantidad": str(cuerpo.cantidad),
                "precio_unitario": str(round(cuerpo.precio_unitario, 2)),
                "imagen_id": imagen_id,
                "tipo_item": "catalogo" if item else "ad_hoc",
                "orden": (max((f.get("orden") or 0 for f in filas), default=-1)) + 1,
                "categoria": categoria,
                "cargo": clasificar_cargo(cuerpo.descripcion, categoria),
                "origen": "provista",
            }
        )
        .execute()
    )
    nueva = creada.data[0]
    await _reordenar(db, cotizacion_id, orden_tras_seccion([*filas, nueva], [str(nueva["id"])], categoria))
    await registrar(
        db, cotizacion_id, usuario, "agregada",
        f"Agregó {formatear_cantidad(cuerpo.cantidad)} × {_nombre(nueva)} a {formatear_moneda(cuerpo.precio_unitario)} c/u "
        f"en {_seccion(categoria)}.",
        item_id=nueva["id"],
    )
    return await cargar_detalle(db, storage, cotizacion_id)


@router.patch("/{cotizacion_id}/partidas/{item_id}", response_model=CotizacionDetalle)
async def editar_partida(
    cotizacion_id: UUID, item_id: UUID, cuerpo: EditarPartida, usuario: Usuario, db: ClienteDB, storage: StorageDep
) -> CotizacionDetalle:
    """Cambia cantidad, precio unitario o sección de una partida (sólo en ProVista)."""
    await _editable(db, cotizacion_id, usuario)
    fila = await _partida(db, cotizacion_id, item_id)
    if fila.get("eliminada"):
        raise HTTPException(status.HTTP_409_CONFLICT, "La partida se quitó de la cotización; restáurala para editarla.")
    cambios: dict[str, Any] = {}
    nombre = _nombre(fila)
    registros: list[tuple[str, str]] = []
    if cuerpo.cantidad is not None and abs(cuerpo.cantidad - float(fila["cantidad"])) >= 0.0005:
        cambios["cantidad"] = str(cuerpo.cantidad)
        registros.append(("cantidad", f"Cambió la cantidad de {nombre}: {formatear_cantidad(float(fila['cantidad']))} → {formatear_cantidad(cuerpo.cantidad)}."))
    if cuerpo.precio_unitario is not None and abs(cuerpo.precio_unitario - float(fila["precio_unitario"])) >= 0.005:
        cambios["precio_unitario"] = str(round(cuerpo.precio_unitario, 2))
        registros.append(("precio", f"Cambió el precio de {nombre}: {formatear_moneda(float(fila['precio_unitario']))} → {formatear_moneda(cuerpo.precio_unitario)}."))
    nuevo_orden = None
    if cuerpo.categoria is not None:
        filas = await _partidas(db, cotizacion_id)
        categoria = seccion_normalizada(cuerpo.categoria, [f.get("categoria") or "" for f in filas if not f.get("eliminada")])
        if categoria != (fila.get("categoria") or ""):
            cambios["categoria"] = categoria
            registros.append(("seccion", f"Movió {nombre} de {_seccion(fila.get('categoria') or '')} a {_seccion(categoria)}."))
            nuevo_orden = orden_tras_seccion(filas, [str(item_id)], categoria)
    if not cambios:
        return await cargar_detalle(db, storage, cotizacion_id)
    await db.table("cotizacion_items").update(cambios).eq("id", str(item_id)).execute()
    await _reordenar(db, cotizacion_id, nuevo_orden)
    for tipo, texto in registros:
        await registrar(db, cotizacion_id, usuario, tipo, texto, item_id=item_id)
    return await cargar_detalle(db, storage, cotizacion_id)


@router.delete("/{cotizacion_id}/partidas/{item_id}", response_model=CotizacionDetalle)
async def quitar_partida(
    cotizacion_id: UUID, item_id: UUID, usuario: Usuario, db: ClienteDB, storage: StorageDep
) -> CotizacionDetalle:
    """Quita una partida. Si vino del sistema se puede restaurar; si se agregó aquí, se borra."""
    await _editable(db, cotizacion_id, usuario)
    fila = await _partida(db, cotizacion_id, item_id)
    if fila.get("origen") == "provista":
        await db.table("cotizacion_items").delete().eq("id", str(item_id)).execute()
    else:
        await db.table("cotizacion_items").update({"eliminada": True, "compuesto_id": None}).eq("id", str(item_id)).execute()
    await _limpiar_compuesto(db, fila.get("compuesto_id"))
    await registrar(
        db, cotizacion_id, usuario, "quitada",
        f"Quitó {formatear_cantidad(float(fila['cantidad']))} × {_nombre(fila)}"
        + (" (se había agregado en ProVista)." if fila.get("origen") == "provista" else "."),
        item_id=item_id,
    )
    return await cargar_detalle(db, storage, cotizacion_id)


@router.post("/{cotizacion_id}/partidas/{item_id}/restaurar", response_model=CotizacionDetalle)
async def restaurar_partida(
    cotizacion_id: UUID, item_id: UUID, usuario: Usuario, db: ClienteDB, storage: StorageDep
) -> CotizacionDetalle:
    """Devuelve a la cotización una partida del sistema que se había quitado."""
    await _editable(db, cotizacion_id, usuario)
    fila = await _partida(db, cotizacion_id, item_id)
    if fila.get("eliminada"):
        await db.table("cotizacion_items").update({"eliminada": False}).eq("id", str(item_id)).execute()
        await registrar(db, cotizacion_id, usuario, "restaurada", f"Restauró {_nombre(fila)}.", item_id=item_id)
    return await cargar_detalle(db, storage, cotizacion_id)


@router.put("/{cotizacion_id}/secciones", response_model=CotizacionDetalle)
async def renombrar_seccion(
    cotizacion_id: UUID, cuerpo: RenombrarSeccion, usuario: Usuario, db: ClienteDB, storage: StorageDep
) -> CotizacionDetalle:
    """Renombra una sección. Con el nombre de otra que ya existe, las junta (así se quita una sección)."""
    await _editable(db, cotizacion_id, usuario)
    filas = await _partidas(db, cotizacion_id)
    existentes = [f.get("categoria") or "" for f in filas if not f.get("eliminada")]
    de = cuerpo.de
    if de not in existentes:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La sección no existe en esta cotización.")
    a = seccion_normalizada(cuerpo.a, [e for e in existentes if e != de])
    if a == de:
        return await cargar_detalle(db, storage, cotizacion_id)
    junta = a in existentes
    mover = [str(f["id"]) for f in filas if not f.get("eliminada") and (f.get("categoria") or "") == de]
    await db.table("cotizacion_items").update({"categoria": a}).in_("id", mover).execute()
    if junta:
        await _reordenar(db, cotizacion_id, orden_tras_seccion(filas, mover, a))
    await _renombrar_en_presentacion(db, cotizacion_id, de, a)
    texto = (
        f"Juntó la sección {_seccion(de)} con {_seccion(a)} ({len(mover)} partida{'s' if len(mover) != 1 else ''})."
        if junta
        else f"Renombró la sección {_seccion(de)} a {_seccion(a)}."
    )
    await registrar(db, cotizacion_id, usuario, "seccion", texto, de=de, a=a, partidas=len(mover))
    return await cargar_detalle(db, storage, cotizacion_id)


@router.post("/{cotizacion_id}/alinear", response_model=CotizacionDetalle)
async def marcar_alineada(cotizacion_id: UUID, usuario: Usuario, db: ClienteDB, storage: StorageDep) -> CotizacionDetalle:
    """El vendedor ya aplicó en el sistema principal los cambios hechos aquí: lo de ProVista pasa a ser
    lo del sistema y el aviso desaparece. El SubTotal y el IVA de referencia se actualizan igual."""
    cotizacion = await _editable(db, cotizacion_id, usuario)
    detalle = await cargar_detalle(db, storage, cotizacion_id)
    cambios = len(detalle.alineacion.cambios)
    if not cambios:
        return detalle
    base_nueva = round(sum(i.importe for i in detalle.items), 2)
    referencia: dict[str, Any] = {}
    if cotizacion.get("subtotal_documento") is not None:
        referencia["subtotal_documento"] = str(base_nueva)
    if cotizacion.get("iva_documento") is not None:
        referencia["iva_documento"] = str(round(base_nueva * detalle.tasa_iva, 2))
    await db.rpc("alinear_cotizacion", {"p_cotizacion": str(cotizacion_id)}).execute()
    if referencia:
        await db.table("cotizaciones").update(referencia).eq("id", str(cotizacion_id)).execute()
    await registrar(
        db, cotizacion_id, usuario, "alineada",
        f"Marcó que los cambios ya están en el sistema principal ({cambios} cambio{'s' if cambios != 1 else ''}).",
        cambios=[c.model_dump(mode="json") for c in detalle.alineacion.cambios],
    )
    return await cargar_detalle(db, storage, cotizacion_id)


@router.get("/{cotizacion_id}/cambios", response_model=list[CambioHistorial])
async def historial(cotizacion_id: UUID, usuario: Usuario, db: ClienteDB) -> list[CambioHistorial]:
    """Historial de cambios hechos en Revisar, más recientes primero."""
    await _fila_cotizacion(db, cotizacion_id, "id")
    respuesta = (
        await db.table("cotizacion_cambios")
        .select("*, usuario:perfiles(nombre)")
        .eq("cotizacion_id", str(cotizacion_id))
        .order("creado_en", desc=True)
        .limit(200)
        .execute()
    )
    return [
        CambioHistorial(
            id=f["id"],
            tipo=f["tipo"],
            descripcion=f.get("descripcion") or "",
            datos=f.get("datos") or {},
            creado_en=f["creado_en"],
            usuario_nombre=((f.get("usuario") or {}).get("nombre") or ""),
        )
        for f in respuesta.data or []
    ]
