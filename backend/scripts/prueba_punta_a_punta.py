"""Prueba de humo contra la API en vivo: recorre el criterio de terminado del piloto.

Uso:
  python scripts/prueba_punta_a_punta.py --correo piloto@minimal40.local --contrasena "..." [--api http://127.0.0.1:8000]

Necesita el backend corriendo, el catálogo sembrado y la anon key (se lee de frontend/.env o --anon-key).
Deja el PDF generado en backend/salidas/propuesta_prueba.pdf.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import httpx

RAIZ_BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_BACKEND))

from app.config import obtener_configuracion  # noqa: E402

FIXTURE = RAIZ_BACKEND / "fixtures" / "export_ejemplo.xlsx"
PLACEHOLDER = RAIZ_BACKEND / "fixtures" / "imagenes_ejemplo" / "SIL-002.png"
SALIDA_PDF = RAIZ_BACKEND / "salidas" / "propuesta_prueba.pdf"


def anon_key_desde_env() -> str | None:
    ruta = RAIZ_BACKEND.parent / "frontend" / ".env"
    if not ruta.exists():
        return None
    coincidencia = re.search(r"^VITE_SUPABASE_ANON_KEY=(.+)$", ruta.read_text(encoding="utf-8"), re.MULTILINE)
    return coincidencia.group(1).strip() if coincidencia else None


def iniciar_sesion(supabase_url: str, anon_key: str, correo: str, contrasena: str) -> str:
    respuesta = httpx.post(
        f"{supabase_url}/auth/v1/token?grant_type=password",
        headers={"apikey": anon_key, "Content-Type": "application/json"},
        json={"email": correo, "password": contrasena},
        timeout=30,
    )
    if respuesta.status_code != 200:
        raise SystemExit(f"No se pudo iniciar sesión ({respuesta.status_code}): {respuesta.text[:200]}")
    return respuesta.json()["access_token"]


class Verificador:
    def __init__(self) -> None:
        self.pasos: list[tuple[str, bool, str]] = []

    def ok(self, nombre: str, condicion: bool, detalle: str = "") -> None:
        self.pasos.append((nombre, condicion, detalle))
        print(f"  [{'OK' if condicion else 'FALLO'}] {nombre}{' - ' + detalle if detalle else ''}")

    def resumen(self) -> int:
        fallos = [p for p in self.pasos if not p[1]]
        print(f"\n{len(self.pasos) - len(fallos)} de {len(self.pasos)} verificaciones correctas.")
        return 1 if fallos else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--correo", required=True)
    parser.add_argument("--contrasena", required=True)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--anon-key", default=anon_key_desde_env())
    parser.add_argument("--peticion", default="madera de nogal con asiento de lino crudo")
    args = parser.parse_args()
    if not args.anon_key:
        raise SystemExit("Falta la anon key (--anon-key o VITE_SUPABASE_ANON_KEY en frontend/.env).")

    config = obtener_configuracion()
    v = Verificador()

    print("1. Sesión")
    token = iniciar_sesion(config.supabase_url, args.anon_key, args.correo, args.contrasena)
    v.ok("Inicio de sesión con Supabase Auth", bool(token))
    api = httpx.Client(base_url=f"{args.api}/api", headers={"Authorization": f"Bearer {token}"}, timeout=180)

    print("2. Salud")
    salud = api.get("/salud")
    v.ok("GET /salud", salud.status_code == 200, salud.text)

    print("3. Subir export")
    with open(FIXTURE, "rb") as archivo:
        creada = api.post("/cotizaciones", files={"archivo": (FIXTURE.name, archivo, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    v.ok("POST /cotizaciones", creada.status_code == 201, creada.text[:200] if creada.status_code != 201 else "")
    if creada.status_code != 201:
        return v.resumen()
    cot = creada.json()
    cot_id = cot["id"]
    estados = {i["codigo_origen"] or "(sin código)": i["estado"] for i in cot["items"]}
    v.ok("Cliente y referencia leídos", cot["nombre_cliente"] == "Hacienda San Pedro Eventos" and cot["referencia_externa"] == "COT-2026-0142")
    v.ok("12 ítems creados", cot["total_items"] == 12, f"{cot['total_items']} ítems")
    v.ok("Ítems con oficial quedan 'sugerida'", estados.get("SIL-001") == "sugerida" and estados.get("MES-002") == "sugerida", str(estados))
    v.ok("XXX-999 y sin código quedan ad hoc sin imagen", estados.get("XXX-999") == "falta_imagen" and estados.get("(sin código)") == "falta_imagen")
    v.ok("TAR-001 (catálogo sin foto) queda pendiente", estados.get("TAR-001") == "falta_imagen")
    v.ok("Pendientes contados", cot["items_pendientes"] == 3, f"{cot['items_pendientes']} pendientes")
    v.ok("URLs firmadas presentes", all(i["imagen"]["url"] for i in cot["items"] if i["imagen"]))

    lista = api.get("/cotizaciones")
    v.ok("GET /cotizaciones incluye la nueva", lista.status_code == 200 and any(c["id"] == cot_id for c in lista.json()))

    def item_por_codigo(detalle: dict, codigo: str) -> dict:
        return next(i for i in detalle["items"] if (i["codigo_origen"] or "") == codigo)

    print("4. Elegir variante de biblioteca (SIL-001)")
    silla = item_por_codigo(cot, "SIL-001")
    imagenes = api.get(f"/catalogo/items/{silla['item_id']}/imagenes").json()
    v.ok("Biblioteca ordenada: oficial primero", imagenes and imagenes[0]["tipo"] == "oficial", f"{len(imagenes)} imágenes")
    variante = next((i for i in imagenes if i["tipo"] == "variante"), None)
    v.ok("Existe una variante", variante is not None)
    if variante:
        cot = api.patch(f"/cotizaciones/{cot_id}/items/{silla['id']}", json={"imagen_id": variante["id"]}).json()
        v.ok("Estado pasa a 'variante'", item_por_codigo(cot, "SIL-001")["estado"] == "variante")
        usos = next(i for i in api.get(f"/catalogo/items/{silla['item_id']}/imagenes").json() if i["id"] == variante["id"])["usos"]
        v.ok("usos de la variante incrementado", usos >= 1, f"usos={usos}")

    print("5. Subir imagen nueva para un ítem de catálogo sin foto (TAR-001)")
    tarima = item_por_codigo(cot, "TAR-001")
    with open(PLACEHOLDER, "rb") as archivo:
        subida = api.post("/imagenes", data={"item_id": tarima["item_id"], "etiquetas": "prueba, tarima"}, files={"archivo": ("tarima.png", archivo, "image/png")})
    v.ok("POST /imagenes", subida.status_code == 201, subida.text[:200] if subida.status_code != 201 else "")
    if subida.status_code == 201:
        cot = api.patch(f"/cotizaciones/{cot_id}/items/{tarima['id']}", json={"imagen_id": subida.json()["id"]}).json()
        v.ok("TAR-001 resuelto con la imagen subida", item_por_codigo(cot, "TAR-001")["estado"] == "variante")

    print("6. Subir foto para el ítem ad hoc (sin código)")
    adhoc = item_por_codigo(cot, "")
    with open(PLACEHOLDER, "rb") as archivo:
        subida = api.post("/imagenes", files={"archivo": ("letrero.png", archivo, "image/png")})
    v.ok("POST /imagenes sin item_id", subida.status_code == 201, subida.text[:200] if subida.status_code != 201 else "")
    if subida.status_code == 201:
        cot = api.patch(f"/cotizaciones/{cot_id}/items/{adhoc['id']}", json={"imagen_id": subida.json()["id"]}).json()
        v.ok("Ítem ad hoc resuelto", item_por_codigo(cot, "")["estado"] == "variante")

    print(f"7. Generar 4 opciones con IA (MES-002, proveedor={config.proveedor_imagenes})")
    mesa = item_por_codigo(cot, "MES-002")
    oficial = next(i for i in api.get(f"/catalogo/items/{mesa['item_id']}/imagenes").json() if i["tipo"] == "oficial")
    generadas = api.post("/imagenes/generar", json={"item_id": mesa["item_id"], "imagen_base_id": oficial["id"], "peticion": args.peticion})
    v.ok("POST /imagenes/generar", generadas.status_code == 200, generadas.text[:200] if generadas.status_code != 200 else "")
    if generadas.status_code == 200:
        opciones = generadas.json()["imagenes"]
        v.ok("Devuelve 4 imágenes 'generada' con URL", len(opciones) == config.variantes_por_generacion and all(o["tipo"] == "generada" and o["url"] for o in opciones))
        cot = api.patch(f"/cotizaciones/{cot_id}/items/{mesa['id']}", json={"imagen_id": opciones[0]["id"]}).json()
        item_mesa = item_por_codigo(cot, "MES-002")
        v.ok("MES-002 queda como render conceptual", item_mesa["estado"] == "render_conceptual" and item_mesa["es_render_conceptual"] is True)

    print("8. Resumen de biblioteca")
    resumen = api.get("/biblioteca/resumen")
    v.ok("GET /biblioteca/resumen", resumen.status_code == 200, str({k: v_ for k, v_ in resumen.json().items() if k != "items_sin_imagen"}) if resumen.status_code == 200 else resumen.text[:200])

    print("9. Generar el PDF")
    pdf = api.post(f"/cotizaciones/{cot_id}/generar")
    v.ok("POST /cotizaciones/{id}/generar", pdf.status_code == 200, pdf.text[:300] if pdf.status_code != 200 else pdf.json()["ruta_storage"])
    if pdf.status_code == 200:
        descarga = httpx.get(pdf.json()["url"], timeout=60)
        es_pdf = descarga.status_code == 200 and descarga.content[:5] == b"%PDF-"
        v.ok("La URL firmada devuelve un PDF", es_pdf, f"{len(descarga.content)} bytes")
        if es_pdf:
            SALIDA_PDF.parent.mkdir(exist_ok=True)
            SALIDA_PDF.write_bytes(descarga.content)
            print(f"  PDF guardado en {SALIDA_PDF}")
        detalle = api.get(f"/cotizaciones/{cot_id}").json()
        v.ok("Estado de la cotización = 'generada'", detalle["estado"] == "generada")

    print(f"\nCotización de prueba: {args.api.replace('8000', '5173')}/cotizaciones/{cot_id}")
    return v.resumen()


if __name__ == "__main__":
    sys.exit(main())
