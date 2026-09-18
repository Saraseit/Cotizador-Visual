# Cotizador visual

Herramienta interna de **Minimal 4.0** (Mérida, Yucatán) para convertir el export de cotizaciones del sistema de la empresa en una propuesta visual (PDF con imágenes) para el cliente.

## Deploy en 5 pasos

Sólo necesitas los valores de `INDISPENSABLE.env.example`. Todo lo demás tiene valor por defecto.

1. **Backend en Railway.** Entra a <https://railway.com/new>, elige *Deploy from GitHub repo* y selecciona `Saraseit/Cotizador-Visual`. En el servicio, *Settings → Build*: Builder **Dockerfile**, Dockerfile Path **`backend/Dockerfile`** (Root Directory se queda en la raíz). En *Settings → Deploy*: Healthcheck Path **`/api/salud`**, Restart Policy *On failure*. Estos cuatro campos son el único ajuste manual: Railway ya no lee `railway.toml` en servicios nuevos (ver [docs/DEPLOY.md](docs/DEPLOY.md)).
2. **Variables del backend.** En el mismo servicio abre la pestaña *Variables* → *Raw Editor* y pega (rellenando los valores):

   ```
   SUPABASE_URL=                 # Supabase → Project Settings → API → Project URL
   SUPABASE_SERVICE_ROLE_KEY=    # Supabase → Project Settings → API Keys → service_role
   OPENAI_API_KEY=               # platform.openai.com → API keys (vacío = proveedor simulado)
   ```

   Luego *Settings → Networking → Generate Domain* y copia la URL (la usarás en el paso 4). Espera a que el deploy quede en verde: el healthcheck es `/api/salud`.
3. **Frontend en Vercel.** Entra a <https://vercel.com/new>, importa el mismo repo y en *Root Directory* pulsa *Edit* y elige **`frontend`**. Vercel detecta Vite solo; `frontend/vercel.json` trae el rewrite para React Router. Ese Root Directory es el único ajuste manual (Vercel no lo acepta desde archivo).
4. **Variables del frontend.** En la misma pantalla de importación (o después en *Settings → Environment Variables*) pega:

   ```
   VITE_SUPABASE_URL=            # mismo valor que SUPABASE_URL
   VITE_SUPABASE_ANON_KEY=       # Supabase → Project Settings → API Keys → anon / publishable
   VITE_API_URL=                 # la URL de Railway del paso 2, sin barra final
   ```

   Pulsa *Deploy*. El backend acepta cualquier dominio `*.vercel.app` mientras `ENTORNO` sea `desarrollo` (el valor por defecto), así que no hay que tocar CORS.
5. **Arranque.** En tu máquina, con Python 3.12+:

   ```bash
   pip install -e ./backend
   python backend/scripts/arrancar.py
   ```

   Te pide lo que falte, aplica migraciones pendientes, crea el primer admin, siembra el catálogo de ejemplo si quieres, llama a `/api/salud` del backend desplegado y te deja un resumen. Después entra al frontend con ese admin y abre **Estado**.

Detalles, todas las variables, cómo actualizar y los ajustes manuales que no se pudieron eliminar: [docs/DEPLOY.md](docs/DEPLOY.md).

## Qué hace

1. Ventas arma la cotización en el sistema de la empresa y exporta el archivo (.xlsx o .pdf).
2. Lo sube aquí. La herramienta lee los ítems, los cruza contra el catálogo y asigna la imagen oficial de cada uno desde una biblioteca compartida.
3. El vendedor ajusta sólo lo que falta: elige otra imagen, sube una foto o genera un render conceptual con IA a partir de la foto oficial.
4. Descarga el PDF para el cliente.

Estado: **alfa desplegable**. La identidad de marca del PDF y el "Diseño con IA" (Fase 2) quedan para después.

## Estructura

```
cotizador-visual/
├── README.md
├── INDISPENSABLE.env.example     # las 6 variables sin valor por defecto
├── .env.example                  # todas las variables, con comentario
├── .github/workflows/ci.yml      # pytest, build del frontend e imagen Docker en cada push
├── docs/DEPLOY.md
├── backend/                      # FastAPI + supabase-py + WeasyPrint
│   ├── Dockerfile                # contexto: raíz del repo
│   ├── pyproject.toml
│   ├── app/
│   │   ├── fuentes/              # IBM Plex Sans (OFL) para el PDF
│   │   ├── main.py               # app, CORS, routers
│   │   ├── config.py             # settings con valores por defecto sanos
│   │   ├── auth.py               # validación del JWT de Supabase + perfil
│   │   ├── db/                   # cliente de Supabase y esquemas Pydantic
│   │   ├── routers/              # salud, perfil, cotizaciones, catalogo, imagenes, biblioteca, usuarios
│   │   ├── servicios/            # parser_export, matching, catalogo_texto, render_pdf, proveedor_imagenes, storage
│   │   └── plantillas/propuesta_base.html
│   ├── scripts/
│   │   ├── arrancar.py           # primer arranque en un comando
│   │   ├── importar_inventario.py  # catálogo desde el reporte de existencias del sistema
│   │   ├── importar_medidas.py   # medidas desde los reportes de inventario físico
│   │   ├── cargar_catalogo.py    # seeding idempotente de catálogo e imágenes
│   │   ├── crear_usuario.py      # alta de usuarios desde la terminal
│   │   ├── prueba_punta_a_punta.py  # prueba de humo contra la API real
│   │   ├── generar_placeholders.py
│   │   └── generar_export_ejemplo.py
│   ├── fixtures/
│   │   ├── export_ejemplo.pdf    # export sintético con el formato PDF del sistema (12 partidas)
│   │   ├── export_ejemplo.xlsx   # export sintético en Excel (12 filas)
│   │   ├── catalogo_ejemplo.csv  # 15 ítems de ejemplo
│   │   ├── catalogo_plantilla.csv  # sólo encabezados: para el catálogo real
│   │   └── mapeo_columnas.json   # mapeo configurable del export
│   └── tests/
├── frontend/                     # React 18 + Vite + TypeScript + Tailwind
│   ├── vercel.json               # rewrite para React Router (Root Directory = frontend)
│   └── src/
│       ├── rutas/                # entrar, subir, revisar, generar, catalogo, biblioteca, usuarios, estado
│       ├── componentes/
│       ├── api/                  # cliente HTTP tipado + hooks de TanStack Query
│       └── lib/                  # supabase, sesión, formato
└── supabase/migrations/          # 7 migraciones: esquema, RLS, buckets, catálogo, generaciones, linter
```

## Correr en local

Requisitos: Python 3.12+ (en local funciona con 3.13), Node 20+, un proyecto de Supabase. Para generar PDFs en Windows hace falta el runtime de GTK3 (ver "WeasyPrint en Windows" abajo); en Docker, Railway y CI ya viene todo.

```bash
cp INDISPENSABLE.env.example .env       # rellena los valores; las VITE_* también van en frontend/.env
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -e "./backend[dev]"
python backend/scripts/arrancar.py --sin-salud   # migraciones, primer admin, catálogo de ejemplo

cd backend && uvicorn app.main:app --port 8000   # http://localhost:8000/api/salud y /docs
cd frontend && npm install && npm run dev        # http://localhost:5173
```

`uvicorn --reload` funciona, pero en algunas terminales de Windows el recargador se cuelga tras el primer cambio; si pasa, reinicia a mano.

### Pruebas

```bash
cd backend && pytest
```

Cubren parser (xlsx y pdf con y sin bordes), matching, carga por texto, normalización de imágenes, rutas de Storage, configuración y render del PDF. Las que necesitan WeasyPrint se omiten si faltan sus librerías nativas.

Con el backend corriendo y un admin creado, la prueba de humo recorre el flujo completo contra la API real (subir export, elegir variante, subir fotos, generar y borrar opciones, catálogo, usuarios, PDF a `backend/salidas/`):

```bash
python scripts/prueba_punta_a_punta.py --correo <tu-admin> --contrasena "..."
```

### WeasyPrint en Windows

Instala el runtime de GTK3 desde <https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer> (silencioso: `gtk3-runtime.exe /S /D=C:\Users\<tu-usuario>\AppData\Local\GTK3-Runtime`). El backend lo detecta solo en esa ruta o en `C:\Program Files\GTK3-Runtime Win64`; en otra, define `WEASYPRINT_DLL_DIRECTORIES`. Sin GTK todo funciona salvo generar el PDF, y `/api/salud` lo muestra en rojo.

## Seeding del catálogo

### Desde los reportes del sistema (recomendado)

El catálogo real se carga desde el reporte "EXISTENCIAS DE MATERIALES PARA ALQUILER" que exporta el sistema, y las medidas desde los reportes de inventario físico (INVENTARIO SILLAS, MESAS…). Ambos comandos muestran una vista previa y sólo escriben con `--aplicar`:

```bash
cd backend
python scripts/importar_inventario.py ruta/inventario.pdf                                   # vista previa + salidas/inventario_vista_previa.csv
python scripts/importar_inventario.py ruta/inventario.pdf --aplicar --lista "Precio 1" --desactivar-ejemplo
python scripts/importar_medidas.py "ruta/INVENTARIO SILLAS.pdf" "ruta/INVENTARIO MESAS .pdf" --aplicar
```

- Código: el del inicio de la descripción (el que aparece en las cotizaciones); si no hay, el de la columna CODIGO. Las diferencias se reportan.
- Nombre, categoría (la sección), costo de reposición (REPO) y precio (columna PRECIO, en la lista indicada). Descripción, medidas y etiquetas quedan vacías si el reporte no las trae.
- Artículos sin código: código provisional estable `SC-xxxxxx` con la etiqueta `sin-codigo` (o `--sin-codigo omitir`). Conceptos internos (viáticos, ajuste, coordinación…) se cargan inactivos con la etiqueta `interno`.
- Idempotente y sin borrar: un dato vacío en el reporte nunca pisa lo que ya tenga el catálogo; las medidas sólo se escriben donde el campo esté vacío.

### Desde CSV

Llena `backend/fixtures/catalogo_plantilla.csv` con tu catálogo real (columnas `codigo,nombre,categoria` obligatorias; `descripcion,medidas,etiquetas,costo_reposicion` opcionales, etiquetas separadas por `|`), pon las fotos en una carpeta nombradas por código (`SIL-001.jpg` la oficial, `SIL-001-1.jpg`, `SIL-001-2.jpg` variantes) y corre el comando:

```bash
cd backend
python scripts/cargar_catalogo.py --csv fixtures/catalogo_plantilla.csv --imagenes /ruta/a/las/fotos
```

- Idempotente: los ítems se hacen upsert por código y las imágenes se identifican por su ruta en Storage. Imprime cuántos ítems creó o actualizó, cuántas imágenes subió y qué archivos no pudo asociar.
- El catálogo de ejemplo (15 ítems) se siembra con `--csv fixtures/catalogo_ejemplo.csv --imagenes fixtures/imagenes_ejemplo --crear-placeholders`, que genera PNG grises con el código (TAR-001 y CAR-001 quedan sin foto a propósito para que Biblioteca tenga datos). Es lo que ofrece `arrancar.py`.
- También se puede cargar desde el frontend: **Catálogo → Carga por texto** acepta líneas pegadas desde Excel.

## Pantallas

- **Subir** (`/`): arrastrar el export; propuestas recientes.
- **Revisar** (`/cotizaciones/:id`): tabla con pendientes arriba; "Elegir imagen" abre *Biblioteca* (o *Subir foto* en ítems fuera de catálogo) y *Generar imagen con IA*. Al elegir una de las 4 opciones generadas, las otras 3 se borran. Si se alcanza el tope diario, el aviso ámbar dice cuál límite y cuándo se libera.
- **Generar** (`/cotizaciones/:id/generar`): descarga del PDF; tarjeta "Diseño con IA" en Fase 2.
- **Catálogo** (`/catalogo`): tabla con foto, medidas, etiquetas, un precio por lista y costo de reposición; formulario completo con sección de imágenes (oficial, variantes, generar con IA); carga por texto; listas de precios.
- **Biblioteca** (`/biblioteca`): cinco métricas (incluye generaciones en 24 h) e ítems más cotizados sin foto.
- **Usuarios** (`/usuarios`, admin): alta, rol, contraseña y baja.
- **Estado** (`/estado`, admin): el diagnóstico de `/api/salud` con círculo verde o rojo por dependencia. Lo primero que hay que abrir tras un deploy.

## Cómo funciona

- **Parser** (`servicios/parser_export.py`): lee `fixtures/mapeo_columnas.json`. El sistema de la empresa exporta PDF sin tabla dibujada, con el código dentro del artículo ("1040 - MESA REDONDA…"), descripciones de varias líneas, "Reposición" bajo la cantidad y secciones; la estrategia `renglones` lo lee por posición de las palabras, separa el código con `pdf.codigo_en_descripcion`, toma cliente y número de cotización con `pdf.metadatos` y valida que la suma de partidas dé el SubTotal. Si un PDF no tiene ese formato, prueba tablas por líneas y por texto. Los .xlsx se leen con `hoja`, `fila_encabezados` y `columnas`.
- **Matching** (`servicios/matching.py`): exacto por código normalizado. Con match asigna la imagen oficial; si no hay, la variante con más usos; si no hay ninguna, deja el ítem pendiente. Sin match, el ítem se guarda como `ad_hoc`.
- **Imágenes generadas** (`servicios/proveedor_imagenes.py`): la base se normaliza a PNG RGBA de máximo 1024 px; `ProveedorOpenAI` usa la edición de `gpt-image-1` con `input_fidelity="high"` y un prompt fijo (forma intacta, tres cuartos, fondo neutro, luz lateral) más la petición del vendedor. Sin `OPENAI_API_KEY` actúa `ProveedorSimulado`. Cada llamada se registra en `generaciones` y hay tope diario por usuario y global (429 con la hora de liberación).
- **PDF** (`servicios/render_pdf.py` + `plantillas/propuesta_base.html`): carta, miniaturas incrustadas como data URI, marcador "Sin imagen", etiqueta "Render conceptual" y leyenda al pie.
- **Reglas en base de datos**: un trigger incrementa `imagenes.usos` al asignar una imagen y marca `es_render_conceptual` cuando es `generada`.
- **Auth**: el frontend inicia sesión con Supabase Auth y manda el `access_token`. El backend lo valida (JWKS ES256 o secret HS256, con 60 s de tolerancia de reloj) y usa la service role key para base y Storage aplicando en código las mismas reglas que las políticas RLS. Imágenes y PDFs se sirven con URLs firmadas de 10 minutos.
- **Salud** (`/api/salud`): un renglón por dependencia; 503 sólo si Supabase no responde, para que Railway detecte el arranque y todo lo demás se pueda leer.

## Endpoints

Prefijo `/api`. Todos requieren `Authorization: Bearer <token de Supabase>` salvo `/salud`.

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/salud` | Diagnóstico: Supabase, buckets, WeasyPrint, proveedor, mapeo, catálogo, usuarios |
| POST | `/cotizaciones` | multipart `archivo` → crea cotización + ítems + matching |
| GET | `/cotizaciones` | Cotizaciones del usuario (admin: todas) |
| GET | `/cotizaciones/{id}` | Detalle con ítems, imagen (URL firmada) y estado |
| PATCH | `/cotizaciones/{id}/items/{item_id}` | `{imagen_id}` asigna o quita (`null`) la imagen |
| POST | `/cotizaciones/{id}/generar` | Renderiza el PDF, lo guarda en `exports` y devuelve URL firmada |
| GET | `/perfil/yo` | Perfil del usuario autenticado |
| GET/POST | `/catalogo/items` | Búsqueda con precios e imagen oficial / alta por formulario |
| GET/PATCH | `/catalogo/items/{id}` | Detalle / edición parcial (`precios` reemplaza el conjunto) |
| POST | `/catalogo/items/carga-texto` | `{texto}` con una línea por ítem; upsert por código sin borrar datos existentes |
| GET | `/catalogo/items/{id}/imagenes` | Imágenes del ítem: oficial primero, luego por usos |
| GET/POST | `/catalogo/listas-precios` | Listas de precios |
| PATCH | `/catalogo/listas-precios/{id}` | Renombrar, ordenar o desactivar |
| POST | `/imagenes` | multipart `archivo` (+ `item_id`, `etiquetas`, `tipo`) |
| POST | `/imagenes/generar` | `{imagen_base_id, peticion, item_id?, cotizacion_id?}` → 4 imágenes `generada`; 429 si se alcanzó el tope |
| DELETE | `/imagenes/{id}` | Borra una imagen generada sin asignar (del mismo usuario o admin) |
| GET | `/biblioteca/resumen` | Métricas de la biblioteca |
| GET/POST | `/usuarios` | Admin: lista y alta |
| PATCH/DELETE | `/usuarios/{id}` | Admin: nombre, rol, contraseña; baja |

## Decisiones tomadas

- **Acceso a datos con `supabase-py` (cliente async)** en lugar de SQLAlchemy: un solo cliente para Postgres, Storage y Auth.
- **El backend usa la service role key** y aplica la autorización en código. Las políticas RLS quedan activas para el acceso directo con la anon key.
- **`usos` y `es_render_conceptual` se mantienen con un trigger**, no en Python.
- **Cantidades y precios se exponen como `float`** en la API; la base los guarda como `numeric`.
- **Fila de encabezados del fixture en la fila 5**, con título y datos del cliente en las filas 1-3.
- **Las filas de resumen ("Total", "Subtotal", "IVA") sin código se omiten** al leer el export.
- **Sólo las imágenes `oficial` y `variante` se sugieren automáticamente**; las `generada` nunca se asignan solas.
- **Una imagen oficial por ítem** (índice único).
- **Proveedor `simulado`** para desarrollar sin créditos; es también a lo que cae `openai` sin llave, en vez de fallar el arranque.
- **Miniaturas del PDF como data URI** reducidas a 640 px; **imagen base para IA** normalizada a PNG RGBA de 1024 px.
- **`gpt-image-1` con `quality=medium` e `input_fidelity=high`** por defecto.
- **Sin registro ni recuperación de contraseña** en la app; el admin gestiona usuarios desde la pantalla Usuarios.
- **Listas de precios como tabla propia**; los precios del catálogo son de referencia y en la cotización manda el export.
- **La carga por texto nunca borra datos**: un campo vacío conserva lo existente.
- **Generar con IA sin ítem de catálogo**: para ítems ad hoc la base es la foto subida.
- **Tope de generaciones en tabla `generaciones`**, no en memoria: sobrevive reinicios y cuenta llamadas, no imágenes. Los admin no están exentos.
- **Borrado de generadas no elegidas desde el frontend** con `Promise.allSettled`: si un borrado falla, la elección no se afecta.
- **Validación del JWT tolerante al reloj** (`leeway=60`, sin verificar `iat`).
- **CORS por defecto acepta `*.vercel.app` en desarrollo** para que el primer deploy no requiera configurar dominios; producción lo exige explícito.
- **`/api/salud` devuelve 503 sólo si Supabase falla**: el resto en rojo devuelve 200 con detalle, para que el servicio arranque y se pueda diagnosticar.
- **Migración extra `0007_migraciones_aplicadas`** (no estaba en la lista de la sesión 2): una función que lee `schema_migrations` para que `arrancar.py` sepa qué falta sin necesitar la contraseña de la base. Aplicarlas desde el script sí necesita `SUPABASE_DB_URL` (psycopg); sin ella indica cómo hacerlo a mano.
- **Sin archivos de configuración de Railway ni Vercel en la raíz.** Railway deprecó Config as Code (`railway.toml` no se lee en servicios nuevos) y su Infrastructure as Code sólo se aplica con la CLI; Vercel no acepta el Root Directory desde archivo. Los cuatro campos del servicio en Railway y el Root Directory en Vercel se configuran en el panel una vez, y están en "Deploy en 5 pasos".
- **IBM Plex Sans empaquetada en el repo** (`app/fuentes`, licencia OFL) y copiada a la imagen: el paquete `fonts-ibm-plex` de Debian está en `contrib`, que la imagen slim no habilita.
- **El PDF real del sistema no está en el repo**: es una cotización de un cliente. Las pruebas usan `fixtures/export_ejemplo.pdf`, generado por `scripts/generar_export_pdf_ejemplo.py` con el mismo formato y datos ficticios.
- **Montos sólo con signo `$`** en el formato por renglones: sin esa regla, medidas como "1.80" o "2.44" se confundían con montos.
- **Categoría, importe y costo de reposición** que trae el PDF se leen pero todavía no se guardan: sirven para validar la suma y quedan listos para usarse.
- **Catálogo real cargado desde el reporte de existencias del 18/09/2026**: 792 artículos (708 con código, 84 provisionales, 8 internos inactivos), 709 con costo de reposición, 736 precios en la lista "Precio 1", 157 con medidas. El catálogo de ejemplo quedó desactivado. Los PDFs de inventario no están en el repo.
- **La columna "PRECIO 1.00" va a la lista "Precio 1"**, no a "Público": no coincide con lo que se cotiza (la mesa 1040 está a $1,103 en el inventario y a $1,050 en la cotización 12066).
- **REPO $0.00 y la pareja REPO/PRECIO en $1.00 se tratan como sin dato**; un PRECIO de $0.00 sí se guarda (hay artículos que van incluidos, como las fundas).
- **Medidas con las etiquetas del reporte** ("ancho · largo · alto" en mesas; "respaldo · base respaldo · asiento" en sillas y bancos), sin reinterpretarlas.
- **Códigos con punto y guion pegado** ("2008.5 - SILLA", "7029-TAPETE") se reconocen en inventario y cotizaciones.
- **Codificación UTF-8 con finales de línea LF** (`.gitattributes`).

## Pendientes conocidos

- Probar con más exports reales del sistema (el formato se validó con la cotización 12066: 15 de 16 partidas se reconocen en el catálogo).
- 84 artículos del inventario no tienen código en el sistema (van con código provisional `SC-…`); en las cotizaciones salen como fuera de catálogo hasta que tengan código real.
- Revisar medidas dudosas del reporte físico, por ejemplo la 1046 trae largo 24 cm (¿244?). Las filas 3010 y 3200 del reporte de mesas periqueras venían dañadas y se omitieron.
- El PDF del sistema ya trae la foto de muchas partidas: se podrían extraer para poblar la biblioteca, y la "Reposición" para llenar `costo_reposicion` del catálogo.
- Identidad de marca en `propuesta_base.html`.
- "Diseño con IA" (Fase 2): la tarjeta existe deshabilitada.
- Paginación en la lista de propuestas si crece mucho (hoy las últimas 100).
