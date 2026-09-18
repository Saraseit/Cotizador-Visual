# Cotizador visual

Herramienta interna de **Minimal 4.0** (Mérida, Yucatán) para convertir el export de cotizaciones del sistema de la empresa en una propuesta visual para el cliente.

El flujo que resuelve:

1. Ventas arma la cotización en el sistema de la empresa y exporta el archivo (.xlsx o .pdf).
2. Sube ese archivo aquí. La herramienta lee los ítems, los cruza contra el catálogo y asigna la imagen oficial de cada uno desde una biblioteca compartida.
3. El vendedor ajusta sólo lo que falta: elige otra imagen de la biblioteca, sube una foto o genera un render conceptual con IA a partir de la foto oficial.
4. Descarga el PDF final para el cliente.

Estado: **piloto desplegable**. Las funciones principales funcionan de punta a punta; la identidad de marca del PDF y el "Diseño con IA" (Fase 2) quedan para después.

## Estructura

```
cotizador-visual/
├── README.md
├── .env.example                  # todas las variables, con comentario
├── backend/                      # FastAPI + supabase-py + WeasyPrint
│   ├── Dockerfile                # imagen con Pango/Cairo para WeasyPrint
│   ├── railway.toml
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py               # app, CORS, routers
│   │   ├── config.py             # settings desde variables de entorno
│   │   ├── auth.py               # validación del JWT de Supabase + perfil
│   │   ├── db/                   # cliente de Supabase y esquemas Pydantic
│   │   ├── routers/              # salud, cotizaciones, catalogo, imagenes, biblioteca
│   │   ├── servicios/            # parser_export, matching, render_pdf, proveedor_imagenes, storage
│   │   └── plantillas/propuesta_base.html
│   ├── scripts/
│   │   ├── cargar_catalogo.py    # seeding idempotente de catálogo e imágenes
│   │   ├── generar_placeholders.py
│   │   └── generar_export_ejemplo.py
│   ├── fixtures/
│   │   ├── export_ejemplo.xlsx   # export sintético (12 filas)
│   │   ├── catalogo_ejemplo.csv  # 15 ítems
│   │   └── mapeo_columnas.json   # mapeo configurable del export
│   └── tests/
├── frontend/                     # React 18 + Vite + TypeScript + Tailwind
│   ├── vercel.json               # rewrite para React Router
│   └── src/
│       ├── rutas/                # entrar, subir, revisar, generar, biblioteca
│       ├── componentes/
│       ├── api/                  # cliente HTTP tipado + hooks de TanStack Query
│       └── lib/                  # supabase, sesión, formato
└── supabase/migrations/          # esquema, RLS y buckets
```

## Requisitos

- Python 3.12+ (el Dockerfile usa 3.12; en local funciona con 3.13).
- Node 20+ y npm.
- Un proyecto de Supabase (Postgres + Auth + Storage).
- Para generar PDFs **en local en Windows**: WeasyPrint necesita el runtime de GTK3 (Pango, Cairo). Instálalo desde <https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer> o con MSYS2. Sin él, el backend arranca y todo funciona salvo `POST /cotizaciones/{id}/generar` (devuelve 500 con un mensaje claro) y dos pruebas se omiten. En Docker/Railway ya viene todo.
- Opcional: una API key de OpenAI para generar imágenes. Sin ella, usa `PROVEEDOR_IMAGENES=simulado`.

## Configuración inicial

### 1. Supabase

1. Crea el proyecto (o usa el que ya existe) y copia de *Project Settings → API*: la URL, la **anon/publishable key** y la **service role key**.
2. Aplica las migraciones de `supabase/migrations/` en orden. Dos opciones:
   - Con la CLI: `supabase link --project-ref <ref>` y `supabase db push`.
   - Pegando cada archivo en el *SQL Editor* del dashboard.

   Las migraciones crean las tablas, las políticas RLS, la función `resumen_biblioteca` y los buckets privados `imagenes` y `exports`.
3. Crea los usuarios en *Authentication → Users* (correo y contraseña). No hay registro desde la app. Al primer acceso se les crea su fila en `perfiles` con rol `vendedor`; para hacer admin a alguien, cambia `rol` a `admin` en la tabla.
4. Firma de tokens: en *Project Settings → JWT Keys* revisa si el proyecto usa llaves asimétricas (ES256, por defecto en proyectos nuevos) o el secret heredado (HS256). Con ES256 no hace falta nada más. Con HS256 copia el *Legacy JWT Secret* a `SUPABASE_JWT_SECRET`.

### 2. Variables de entorno

```bash
cp .env.example .env            # backend (se lee desde la raíz o desde backend/)
cp .env.example frontend/.env   # frontend: sólo importan las VITE_*
```

Rellena al menos `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`. Cada variable está explicada en `.env.example`.

## Correr en local

### Backend

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -e "./backend[dev]"
cd backend
uvicorn app.main:app --reload --port 8000
```

- Salud: <http://localhost:8000/api/salud>
- Documentación interactiva: <http://localhost:8000/docs> (usa el botón *Authorize* con un `access_token` de Supabase).

### Frontend

```bash
cd frontend
npm install
npm run dev     # http://localhost:5173
```

### Pruebas

```bash
cd backend
pytest
```

Cubren el parser (xlsx y pdf), el matching y el render del PDF. Las que necesitan WeasyPrint se omiten si faltan sus librerías nativas.

## Seeding del catálogo

```bash
cd backend
python scripts/cargar_catalogo.py --csv fixtures/catalogo_ejemplo.csv --imagenes fixtures/imagenes_ejemplo --crear-placeholders
```

- El CSV lleva columnas `codigo,nombre,categoria`.
- La carpeta de imágenes usa `<codigo>.jpg|png|webp` para la foto oficial y `<codigo>-1.jpg`, `<codigo>-2.jpg` para variantes.
- `--crear-placeholders` genera PNG grises con el código para los ítems sin archivo (desarrollo). Deja TAR-001 y CAR-001 sin imagen a propósito para que la pantalla Biblioteca tenga datos.
- Es idempotente: los ítems se hacen upsert por código y las imágenes se identifican por su ruta en Storage. Al final imprime cuántos ítems creó/actualizó, cuántas imágenes subió y qué archivos no pudo asociar.

Con datos reales: exporta el catálogo a un CSV con esas tres columnas, nombra las fotos con el código y corre el mismo comando sin `--crear-placeholders`.

## Cómo funciona

- **Parser** (`servicios/parser_export.py`): lee `fixtures/mapeo_columnas.json` para saber en qué hoja, fila y columnas están los datos y de qué celdas salen cliente y referencia. Los encabezados se comparan sin acentos ni mayúsculas. Para PDF usa `pdfplumber` con la misma interfaz; el punto de ajuste con el archivo real es `_extraer_tablas_pdf`.
- **Matching** (`servicios/matching.py`): exacto por código normalizado (mayúsculas, sin espacios). Con match asigna la imagen oficial; si no hay, la variante con más usos; si no hay ninguna, deja el ítem pendiente. Sin match, el ítem se guarda como `ad_hoc` sin descartarlo.
- **Imágenes generadas** (`servicios/proveedor_imagenes.py`): interfaz `ProveedorImagenes`; `ProveedorOpenAI` usa el endpoint de edición de `gpt-image-1` con la foto oficial como base, `input_fidelity="high"` y un prompt fijo (forma y proporciones intactas, ángulo de tres cuartos, fondo neutro, luz lateral, sin texto ni personas) más la petición del vendedor. Genera 4 variantes. Si el proveedor falla, la API responde 502 y la cotización no se toca.
- **PDF** (`servicios/render_pdf.py` + `plantillas/propuesta_base.html`): tamaño carta, tabla con miniaturas incrustadas como data URI (reducidas a 640 px), marcador "Sin imagen", etiqueta "Render conceptual" y leyenda al pie cuando aplica.
- **Reglas en base de datos**: un trigger incrementa `imagenes.usos` al asignar una imagen a un ítem y marca `es_render_conceptual` cuando la imagen es `generada`. Así la regla se cumple aunque se escriba desde otro lado.
- **Auth**: el frontend inicia sesión con Supabase Auth y manda el `access_token` como Bearer. El backend lo valida (JWKS o secret HS256) y usa la service role key para la base y Storage, aplicando en código las mismas reglas que las políticas RLS. Las imágenes y PDFs se sirven con URLs firmadas de 10 minutos.

## Despliegue

Nada se despliega automáticamente; estos son los pasos.

### Backend en Railway

1. Nuevo servicio desde el repo de GitHub. En *Settings → Root Directory* pon `backend`. Railway detecta `railway.toml` y construye con el `Dockerfile`.
2. Variables (*Settings → Variables*):

   | Variable | Valor |
   |---|---|
   | `SUPABASE_URL` | URL del proyecto |
   | `SUPABASE_SERVICE_ROLE_KEY` | service role key |
   | `SUPABASE_JWT_SECRET` | sólo si el proyecto firma con HS256 |
   | `PROVEEDOR_IMAGENES` | `openai` |
   | `OPENAI_API_KEY` | API key |
   | `OPENAI_CALIDAD_IMAGENES` | `medium` (o `low` para abaratar) |
   | `CORS_ORIGENES` | `https://<tu-app>.vercel.app` (varios separados por coma) |
   | `ENTORNO` | `produccion` |

   `PORT` lo inyecta Railway. El resto tiene valores por defecto (ver `.env.example`).
3. Genera un dominio público en *Settings → Networking*. El healthcheck está en `/api/salud`.

### Frontend en Vercel

1. Nuevo proyecto desde el repo. *Root Directory* = `frontend`, framework Vite. Build `npm run build`, salida `dist`.
2. Variables:

   | Variable | Valor |
   |---|---|
   | `VITE_SUPABASE_URL` | URL del proyecto |
   | `VITE_SUPABASE_ANON_KEY` | anon/publishable key |
   | `VITE_API_URL` | dominio del backend en Railway, sin barra final |

3. `frontend/vercel.json` ya tiene el rewrite para que React Router maneje las rutas.
4. Vuelve a Railway y agrega el dominio de Vercel a `CORS_ORIGENES`.

### Después del primer deploy

1. Crear los usuarios en Supabase Auth.
2. Correr el seeding con el CSV y las fotos reales (desde tu máquina, con el `.env` apuntando al proyecto).
3. Pedir un export real del sistema y ajustar `backend/fixtures/mapeo_columnas.json` (hoja, fila de encabezados, nombres de columnas, celdas de cliente y referencia). Si el export es PDF, revisar `_extraer_tablas_pdf`.
4. Subir un export, revisar, generar un PDF y validar con ventas.

## Endpoints

Prefijo `/api`. Todos requieren `Authorization: Bearer <token de Supabase>` salvo `/salud`.

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/salud` | Estado del servicio |
| POST | `/cotizaciones` | multipart `archivo` → crea cotización + ítems + matching |
| GET | `/cotizaciones` | Cotizaciones del usuario (admin: todas) |
| GET | `/cotizaciones/{id}` | Detalle con ítems, imagen (URL firmada) y estado |
| PATCH | `/cotizaciones/{id}/items/{item_id}` | `{imagen_id}` asigna o quita (`null`) la imagen |
| POST | `/cotizaciones/{id}/generar` | Renderiza el PDF, lo guarda en `exports` y devuelve URL firmada |
| GET | `/catalogo/items?buscar=` | Búsqueda por código o nombre |
| GET | `/catalogo/items/{id}/imagenes` | Imágenes del ítem: oficial primero, luego por usos |
| POST | `/imagenes` | multipart `archivo` (+ `item_id`, `etiquetas`, `tipo`) |
| POST | `/imagenes/generar` | `{item_id, imagen_base_id, peticion}` → 4 imágenes `generada` |
| GET | `/biblioteca/resumen` | Métricas de la biblioteca |

## Decisiones tomadas

Cosas que no estaban definidas y se resolvieron sobre la marcha:

- **Acceso a datos con `supabase-py` (cliente async)** en lugar de SQLAlchemy: un solo cliente para Postgres, Storage y validación; menos piezas para el piloto.
- **El backend usa la service role key** y aplica la autorización en código (dueño o admin para escribir cotizaciones). Las políticas RLS quedan activas para proteger el acceso directo con la anon key.
- **`usos` y `es_render_conceptual` se mantienen con un trigger** en `cotizacion_items` (ver migración 0001), no en Python, para que la regla sea única.
- **Cantidades y precios se exponen como `float`** en la API (la base los guarda como `numeric`). Es una herramienta de presentación, no contable.
- **Fila de encabezados del fixture en la fila 5** (`fila_encabezados: 5`), con título y datos de cliente en las filas 1-3, para que las celdas B2/B3 del mapeo tengan sentido.
- **Las filas de resumen ("Total", "Subtotal", "IVA") sin código se omiten** al leer el export; las que tienen descripción pero no código se conservan como ítems ad hoc.
- **Sólo las imágenes `oficial` y `variante` se sugieren automáticamente**; las `generada` nunca se asignan sin que el vendedor las elija.
- **Una imagen oficial por ítem** (índice único). Si el seeding encuentra una segunda, la guarda como variante y lo avisa.
- **Proveedor `simulado`** (`PROVEEDOR_IMAGENES=simulado`) para desarrollar el flujo de generación sin gastar créditos: devuelve la imagen base con un tinte y una etiqueta.
- **Las miniaturas del PDF se incrustan como data URI** reducidas a 640 px, para que WeasyPrint no dependa de la red y el archivo no pese demasiado.
- **`gpt-image-1` con `quality=medium` e `input_fidelity=high`** por defecto; la calidad se cambia por variable de entorno.
- **Sin registro de usuarios ni recuperación de contraseña** en la app; se gestiona desde Supabase.
- **Codificación de commits y archivos en UTF-8 con finales de línea LF** (`.gitattributes`), para que el Dockerfile y los scripts funcionen igual en Windows y Linux.

## Pendientes conocidos

- Ajustar `mapeo_columnas.json` (y posiblemente `_extraer_tablas_pdf`) con el export real.
- Identidad de marca en `propuesta_base.html`.
- "Diseño con IA" (Fase 2): la tarjeta existe deshabilitada en la pantalla Generar.
- Paginación y búsqueda en la lista de propuestas si crece mucho (hoy se muestran las últimas 100).
