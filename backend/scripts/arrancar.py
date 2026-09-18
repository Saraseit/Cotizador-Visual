"""Arranque del piloto en un solo comando, contra el proyecto real de Supabase.

    python backend/scripts/arrancar.py

Pasos (todos idempotentes; correrlo dos veces no rompe nada):
  1. Verifica las variables indispensables; las que falten se piden por teclado y se guardan en .env
     (y las VITE_* también en frontend/.env).
  2. Compara supabase/migrations/ con lo aplicado y aplica las pendientes. Para aplicarlas necesita la
     URL de conexión a Postgres (SUPABASE_DB_URL, opcional); sin ella indica cómo hacerlo a mano.
  3. Crea el primer usuario admin (si ya hay uno, lo dice y sólo ofrece crear otro).
  4. Pregunta si sembrar el catálogo de ejemplo (15 ítems con marcadores de posición).
  5. Llama a /api/salud del backend desplegado e imprime el diagnóstico.
  6. Resume qué quedó listo y qué falta.

Opciones para correrlo sin preguntas (útil en pruebas): --correo, --contrasena, --nombre,
--sembrar / --no-sembrar, --api URL, --db-url URL, --sin-salud.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

RAIZ_BACKEND = Path(__file__).resolve().parent.parent
RAIZ_REPO = RAIZ_BACKEND.parent
RUTA_ENV = RAIZ_REPO / ".env"
RUTA_ENV_FRONTEND = RAIZ_REPO / "frontend" / ".env"
DIR_MIGRACIONES = RAIZ_REPO / "supabase" / "migrations"
sys.path.insert(0, str(RAIZ_BACKEND))

INDISPENSABLES = [
    ("SUPABASE_URL", "Supabase → Project Settings → API → Project URL", True),
    ("SUPABASE_SERVICE_ROLE_KEY", "Supabase → Project Settings → API Keys → service_role", True),
    ("VITE_SUPABASE_URL", "mismo valor que SUPABASE_URL", True),
    ("VITE_SUPABASE_ANON_KEY", "Supabase → Project Settings → API Keys → anon / publishable", True),
    ("OPENAI_API_KEY", "platform.openai.com → API keys (vacío = proveedor simulado)", False),
]
PATRON_MIGRACION = re.compile(r"^(?P<version>\d+)_(?P<nombre>.+)\.sql$")


@dataclass
class Resumen:
    listo: list[str] = field(default_factory=list)
    pendiente: list[str] = field(default_factory=list)

    def imprimir(self) -> None:
        print("\n" + "=" * 64)
        print("RESUMEN")
        print("=" * 64)
        for linea in self.listo:
            print(f"  [OK] {linea}")
        for linea in self.pendiente:
            print(f"  [..] {linea}")
        if not self.pendiente:
            print("\nTodo listo. Abre el frontend, entra con el admin y revisa /estado.")
        else:
            print("\nQuedan pendientes arriba marcados con [..].")


def titulo(numero: int, texto: str) -> None:
    print(f"\n--- Paso {numero}: {texto} ---")


def preguntar(texto: str, por_defecto: str = "", secreto: bool = False) -> str:
    sufijo = f" [{por_defecto}]" if por_defecto else ""
    try:
        valor = (getpass.getpass(f"{texto}{sufijo}: ") if secreto else input(f"{texto}{sufijo}: ")).strip()
    except EOFError:
        valor = ""
    return valor or por_defecto


def confirmar(texto: str, por_defecto: bool = False) -> bool:
    respuesta = preguntar(f"{texto} (s/n)", "s" if por_defecto else "n").lower()
    return respuesta.startswith("s")


# ---------------------------------------------------------------------------
# Paso 1: variables
# ---------------------------------------------------------------------------

def leer_env(ruta: Path) -> dict[str, str]:
    valores: dict[str, str] = {}
    if not ruta.exists():
        return valores
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        limpia = linea.strip()
        if not limpia or limpia.startswith("#") or "=" not in limpia:
            continue
        clave, _, valor = limpia.partition("=")
        valores[clave.strip()] = valor.split(" #")[0].strip().strip('"').strip("'")
    return valores


def escribir_env(ruta: Path, cambios: dict[str, str]) -> None:
    """Actualiza las claves existentes y agrega las nuevas al final, sin tocar comentarios."""
    lineas = ruta.read_text(encoding="utf-8").splitlines() if ruta.exists() else []
    pendientes = dict(cambios)
    for indice, linea in enumerate(lineas):
        clave = linea.split("=", 1)[0].strip()
        if not linea.strip().startswith("#") and "=" in linea and clave in pendientes:
            lineas[indice] = f"{clave}={pendientes.pop(clave)}"
    for clave, valor in pendientes.items():
        lineas.append(f"{clave}={valor}")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def paso_variables(resumen: Resumen) -> dict[str, str]:
    titulo(1, "variables indispensables")
    env = leer_env(RUTA_ENV)
    env.update({k: v for k, v in leer_env(RUTA_ENV_FRONTEND).items() if k.startswith("VITE_") and k not in env})
    for clave, donde, obligatoria in INDISPENSABLES:
        if env.get(clave) or (not obligatoria and clave in env):
            print(f"  {clave}: presente")
            continue
        if clave == "VITE_SUPABASE_URL" and env.get("SUPABASE_URL"):
            env[clave] = env["SUPABASE_URL"]
            print(f"  {clave}: copiada de SUPABASE_URL")
            continue
        print(f"  {clave}: falta. Se consigue en: {donde}")
        valor = preguntar(f"  Pega {clave}" + (" (Enter para dejar vacío)" if not obligatoria else ""), secreto="KEY" in clave)
        if obligatoria and not valor:
            raise SystemExit(f"{clave} es obligatoria; sin ella no se puede continuar.")
        env[clave] = valor

    escribir_env(RUTA_ENV, {k: env.get(k, "") for k, _, _ in INDISPENSABLES})
    escribir_env(RUTA_ENV_FRONTEND, {k: v for k, v in env.items() if k.startswith("VITE_")})
    for clave, valor in env.items():
        os.environ.setdefault(clave, valor)
    print(f"  Variables guardadas en {RUTA_ENV} y {RUTA_ENV_FRONTEND}")
    resumen.listo.append("Variables indispensables en .env y frontend/.env")
    if not env.get("OPENAI_API_KEY"):
        resumen.pendiente.append("OPENAI_API_KEY vacía: la generación de imágenes usa el proveedor simulado")
    return env


# ---------------------------------------------------------------------------
# Paso 2: migraciones
# ---------------------------------------------------------------------------

def migraciones_locales() -> list[tuple[str, str, Path]]:
    salida = []
    for ruta in sorted(DIR_MIGRACIONES.glob("*.sql")):
        coincidencia = PATRON_MIGRACION.match(ruta.name)
        if coincidencia:
            salida.append((coincidencia.group("version"), coincidencia.group("nombre"), ruta))
    return salida


async def nombres_aplicados_por_rpc(db) -> set[str] | None:
    try:
        respuesta = await db.rpc("migraciones_aplicadas", {}).execute()
    except Exception:
        return None
    return {fila["nombre"] for fila in respuesta.data or []}


def conexion_postgres(db_url: str):
    try:
        import psycopg
    except ImportError as error:  # pragma: no cover
        raise SystemExit("Falta psycopg: pip install 'psycopg[binary]' (está en pyproject, reinstala el backend).") from error
    return psycopg.connect(db_url, autocommit=False)


def nombres_aplicados_por_postgres(db_url: str) -> set[str]:
    with conexion_postgres(db_url) as conexion:
        filas = conexion.execute("select name from supabase_migrations.schema_migrations").fetchall()
    return {str(f[0]) for f in filas}


def aplicar_con_postgres(db_url: str, pendientes: list[tuple[str, str, Path]]) -> None:
    with conexion_postgres(db_url) as conexion:
        conexion.execute("create schema if not exists supabase_migrations")
        conexion.execute(
            "create table if not exists supabase_migrations.schema_migrations "
            "(version text primary key, statements text[], name text)"
        )
        for version, nombre, ruta in pendientes:
            sql = ruta.read_text(encoding="utf-8")
            print(f"  aplicando {ruta.name} ...", end=" ", flush=True)
            conexion.execute(sql)
            conexion.execute(
                "insert into supabase_migrations.schema_migrations (version, name, statements) values (%s, %s, %s) "
                "on conflict (version) do nothing",
                (version, nombre, [sql]),
            )
            conexion.commit()
            print("ok")


async def paso_migraciones(db, resumen: Resumen, db_url: str | None) -> None:
    titulo(2, "migraciones")
    locales = migraciones_locales()
    aplicadas: set[str] | None = None
    if db_url:
        try:
            aplicadas = nombres_aplicados_por_postgres(db_url)
        except Exception as error:
            print(f"  No se pudo consultar Postgres con SUPABASE_DB_URL: {str(error)[:160]}")
    if aplicadas is None:
        aplicadas = await nombres_aplicados_por_rpc(db)

    if aplicadas is None:
        print("  No se pudo consultar qué migraciones están aplicadas (la función migraciones_aplicadas no existe todavía).")
        print("  Aplica a mano, en orden, en Supabase → SQL Editor, o con `supabase db push`:")
        for _, _, ruta in locales:
            print(f"    - supabase/migrations/{ruta.name}")
        resumen.pendiente.append("Migraciones: aplicar a mano (no se pudo consultar el estado)")
        return

    pendientes = [m for m in locales if m[1] not in aplicadas]
    print(f"  {len(locales) - len(pendientes)} de {len(locales)} migraciones ya aplicadas.")
    if not pendientes:
        resumen.listo.append("Migraciones al día")
        return
    for _, _, ruta in pendientes:
        print(f"  pendiente: {ruta.name}")

    if not db_url:
        db_url = preguntar(
            "  Para aplicarlas aquí pega la URL de Postgres (Supabase → Connect → Session pooler, con tu contraseña) "
            "o Enter para hacerlo a mano"
        )
        if db_url:
            escribir_env(RUTA_ENV, {"SUPABASE_DB_URL": db_url})
    if not db_url:
        print("  Aplícalas en orden en Supabase → SQL Editor (pegando cada archivo) o con `supabase db push`.")
        resumen.pendiente.append(f"Migraciones pendientes: {', '.join(r.name for _, _, r in pendientes)}")
        return
    try:
        aplicar_con_postgres(db_url, pendientes)
        resumen.listo.append(f"Migraciones aplicadas: {', '.join(r.name for _, _, r in pendientes)}")
    except Exception as error:
        print(f"  Error al aplicar: {str(error)[:300]}")
        resumen.pendiente.append("Migraciones: falló la aplicación automática; revisa el error y aplica a mano")


# ---------------------------------------------------------------------------
# Paso 3: primer admin
# ---------------------------------------------------------------------------

async def paso_admin(db, resumen: Resumen, args: argparse.Namespace) -> None:
    titulo(3, "primer usuario administrador")
    from scripts.crear_usuario import ejecutar as crear_usuario

    try:
        admins = await db.table("perfiles").select("id, nombre").eq("rol", "admin").execute()
    except Exception as error:
        print(f"  No se pudo consultar perfiles ({str(error)[:120]}); ¿faltan migraciones?")
        resumen.pendiente.append("Primer admin: no se pudo verificar (perfiles no disponible)")
        return
    if admins.data:
        print(f"  Ya hay {len(admins.data)} admin(s): {', '.join(a['nombre'] or a['id'] for a in admins.data)}")
        if not (args.correo or confirmar("  ¿Crear otro admin?", False)):
            resumen.listo.append("Usuario admin existente")
            return
    correo = args.correo or preguntar("  Correo del admin")
    contrasena = args.contrasena or preguntar("  Contraseña (mínimo 8 caracteres)", secreto=True)
    nombre = args.nombre or preguntar("  Nombre", correo.split("@")[0] if correo else "")
    if not correo or len(contrasena) < 8:
        print("  Correo vacío o contraseña corta: se omite.")
        resumen.pendiente.append("Primer admin: crear con scripts/crear_usuario.py --rol admin")
        return
    await crear_usuario(correo, contrasena, nombre, "admin")
    resumen.listo.append(f"Admin {correo} listo")


# ---------------------------------------------------------------------------
# Paso 4: seeding
# ---------------------------------------------------------------------------

async def paso_seeding(resumen: Resumen, args: argparse.Namespace) -> None:
    titulo(4, "catálogo de ejemplo")
    if args.sembrar is None:
        sembrar = confirmar("  ¿Sembrar el catálogo de ejemplo (15 ítems con marcadores de posición)?", True)
    else:
        sembrar = args.sembrar
    if not sembrar:
        print("  Omitido. Para tu catálogo real: llena fixtures/catalogo_plantilla.csv y corre scripts/cargar_catalogo.py")
        resumen.pendiente.append("Catálogo real: fixtures/catalogo_plantilla.csv + scripts/cargar_catalogo.py")
        return
    from scripts.cargar_catalogo import ejecutar as cargar
    from scripts.generar_placeholders import crear_placeholders

    csv = RAIZ_BACKEND / "fixtures" / "catalogo_ejemplo.csv"
    carpeta = RAIZ_BACKEND / "fixtures" / "imagenes_ejemplo"
    crear_placeholders(csv, carpeta, omitir={"TAR-001", "CAR-001"}, con_variante={"SIL-001", "MES-002"})
    reporte = await cargar(csv, carpeta)
    reporte.imprimir()
    resumen.listo.append(f"Catálogo de ejemplo: {reporte.items_creados} creados, {reporte.items_actualizados} actualizados")


# ---------------------------------------------------------------------------
# Paso 5: salud del backend desplegado
# ---------------------------------------------------------------------------

def paso_salud(resumen: Resumen, args: argparse.Namespace, env: dict[str, str]) -> None:
    titulo(5, "salud del backend")
    if args.sin_salud:
        print("  Omitido (--sin-salud).")
        return
    import httpx

    url = args.api or preguntar("  URL del backend (Railway → Settings → Networking)", env.get("VITE_API_URL") or "http://localhost:8000")
    url = url.rstrip("/")
    try:
        respuesta = httpx.get(f"{url}/api/salud", timeout=60)
        datos = respuesta.json()
    except Exception as error:
        print(f"  No responde: {str(error)[:160]}")
        resumen.pendiente.append(f"Backend en {url}: no respondió a /api/salud")
        return
    print(f"  HTTP {respuesta.status_code} · estado {datos.get('estado')} · versión {datos.get('version')} · proveedor {datos.get('proveedor_imagenes')}")
    for clave, verificacion in (datos.get("verificaciones") or {}).items():
        marca = "OK" if verificacion.get("ok") else "!!"
        print(f"    [{marca}] {clave}: {verificacion.get('detalle')}")
    if datos.get("estado") == "ok":
        resumen.listo.append(f"Backend en {url} con todas las verificaciones en verde")
    else:
        fallidas = [k for k, v in (datos.get("verificaciones") or {}).items() if not v.get("ok")]
        resumen.pendiente.append(f"Backend en {url}: revisar {', '.join(fallidas)}")
    if env.get("VITE_API_URL", "").rstrip("/") != url:
        escribir_env(RUTA_ENV, {"VITE_API_URL": url})
        escribir_env(RUTA_ENV_FRONTEND, {"VITE_API_URL": url})


# ---------------------------------------------------------------------------

async def principal(args: argparse.Namespace) -> int:
    resumen = Resumen()
    env = paso_variables(resumen)

    # Con las variables ya en el entorno se puede crear el cliente de Supabase.
    from app.config import obtener_configuracion
    from app.db.cliente import crear_cliente

    obtener_configuracion.cache_clear()
    db = await crear_cliente(obtener_configuracion())

    await paso_migraciones(db, resumen, args.db_url or env.get("SUPABASE_DB_URL") or os.environ.get("SUPABASE_DB_URL"))
    await paso_admin(db, resumen, args)
    await paso_seeding(resumen, args)
    paso_salud(resumen, args, leer_env(RUTA_ENV))

    titulo(6, "resumen")
    resumen.imprimir()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--correo")
    parser.add_argument("--contrasena")
    parser.add_argument("--nombre")
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--sembrar", dest="sembrar", action="store_true", default=None)
    grupo.add_argument("--no-sembrar", dest="sembrar", action="store_false")
    parser.add_argument("--api", help="URL del backend desplegado")
    parser.add_argument("--db-url", help="URL de Postgres para aplicar migraciones")
    parser.add_argument("--sin-salud", action="store_true")
    args = parser.parse_args()
    sys.exit(asyncio.run(principal(args)))


if __name__ == "__main__":
    main()
