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

5. Si el cliente lo pide, arma la presentación editorial con la marca de Minimal 4.0, en la plantilla que elija y, si hace falta, en inglés y en dólares.

Estado: **en uso con piloto**. El PDF base es neutro; la identidad de marca vive en la presentación editorial.

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
│   │   ├── marca/               # logotipo y monograma de Minimal 4.0 (PNG)
│   │   ├── routers/              # salud, perfil, cotizaciones, presentaciones, plantillas, catalogo, imagenes, biblioteca, usuarios
│   │   ├── servicios/            # parser_export, matching, cargos, fotos_pdf, render_pdf, presentacion, idiomas,
│   │   │                         # ia_texto, proveedor_imagenes, catalogo_texto, storage
│   │   └── plantillas/           # propuesta_base.html y presentacion_editorial.html
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
│       ├── rutas/                # entrar, subir, revisar, generar, presentacion, propuestas, catalogo,
│       │                         # biblioteca, usuarios, estado
│       ├── componentes/
│       ├── api/                  # cliente HTTP tipado + hooks de TanStack Query
│       └── lib/                  # supabase, sesión, formato
└── supabase/migrations/          # 11 migraciones: esquema, RLS, buckets, catálogo, generaciones, linter,
                                  # orden y cargos, presentaciones, historial de PDF, plantillas y paletas
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

- **Subir** (`/`): arrastrar el PDF de la cotización (sólo PDF); propuestas recientes. Las fotos que trae el PDF se guardan solas en la biblioteca de cada artículo y Revisar avisa cuántas fueron nuevas.
- **Propuestas** (`/propuestas`): todas las cotizaciones (las propias; un admin ve todas), con filtro Todas/En revisión/Generadas y búsqueda por cliente o referencia. Cada fila se expande y muestra el historial completo de PDF generados de esa cotización —cada propuesta base y cada presentación editorial, con su fecha— con "Abrir para imprimir" (visor del navegador) y "Descargar" (fuerza guardar el archivo). Si no hay ninguno, enlaza de vuelta a Revisar.
- **Revisar** (`/cotizaciones/:id`): tabla con pendientes arriba; "Elegir imagen" abre *Biblioteca* (o *Subir foto* en ítems fuera de catálogo) y *Generar imagen con IA*. Al elegir una de las 4 opciones generadas, las otras 3 se borran. Si se alcanza el tope diario, el aviso ámbar dice cuál límite y cuándo se libera.
  - *Pendientes* muestra sólo las partidas sin imagen. *Todos* muestra el orden de impresión agrupado por las secciones del PDF: se arrastra una partida por su asa (dentro de su sección) o una sección completa por su título; también con teclado (Espacio y flechas). El orden se guarda al soltar.
  - La descripción de cada partida se edita ahí mismo: es una nota para esa cotización, no toca el catálogo ni el sistema de la empresa. Si la escribes tú, es lo que se imprime y no se manda a traducir.
  - Columna *Tipo* (Partida, Flete o Montaje) y bloque *Flete y montaje*: los cargos no se imprimen como partida, se suman abajo. Al lado, los totales tal como saldrán: Subtotal, Flete, Montaje, IVA (o "más IVA") y Total.
- **Generar** (`/cotizaciones/:id/generar`): descarga del PDF base y entrada a la presentación editorial.
- **Presentación editorial** (`/cotizaciones/:id/presentacion`, piloto): el vendedor escribe sus indicaciones (de ahí sale el prompt de los montajes), el título y el evento, elige tipografía de títulos (Everett o Bebas Neue), paleta y si se muestran los precios; pone las fotos de ambientación (portada, manifiesto y cierre) y, por sección, el título editorial, el texto en tres columnas y el montaje: subido, elegido de la biblioteca o generado con IA ("Generar los N montajes que faltan" los hace todos). "Generar PDF" guarda y muestra la presentación en la misma pantalla.
  - *Plantilla*: subir una imagen de inspiración crea una plantilla reutilizable; la IA la mira y propone composición (editorial, revista o catálogo), paleta, tipografía, tamaño de títulos y piezas por página. Aplicarla copia esos parámetros a la propuesta, que después se ajustan a mano sin tocar la plantilla.
  - *Ajustes del diseño*: los mismos parámetros sueltos, más doce paletas de la app y las que guarde el equipo (se crean con los tres colores y un nombre).
  - *Precios, moneda e idioma*: ocultar precios, presentar en dólares con el tipo de cambio que pongas, y cambiar el idioma a inglés (con el botón *Traducir con IA*).
- **Catálogo** (`/catalogo`): tabla con foto, medidas, etiquetas, un precio por lista y costo de reposición; formulario completo con sección de imágenes (oficial, variantes, generar con IA); carga por texto; listas de precios.
- **Biblioteca** (`/biblioteca`): cinco métricas (incluye generaciones en 24 h) e ítems más cotizados sin foto.
- **Usuarios** (`/usuarios`, admin): alta, rol, contraseña y baja.
- **Tema claro/oscuro**: botón en la barra superior (y en el login) que alterna Automático → Claro → Oscuro. Automático sigue al sistema operativo y reacciona si éste cambia; la elección se recuerda en el navegador. El PDF de la propuesta no cambia: siempre es claro.
- **Estado** (`/estado`, admin): el diagnóstico de `/api/salud` con círculo verde o rojo por dependencia. Lo primero que hay que abrir tras un deploy.

## Cómo funciona

- **Parser** (`servicios/parser_export.py`): lee `fixtures/mapeo_columnas.json`. El sistema de la empresa exporta PDF sin tabla dibujada, con el código dentro del artículo ("1040 - MESA REDONDA…"), descripciones de varias líneas, "Reposición" bajo la cantidad y secciones; la estrategia `renglones` lo lee por posición de las palabras, separa el código con `pdf.codigo_en_descripcion`, toma cliente y número de cotización con `pdf.metadatos` y valida que la suma de partidas dé el SubTotal. Si un PDF no tiene ese formato, prueba tablas por líneas y por texto. Los .xlsx se leen con `hoja`, `fila_encabezados` y `columnas`.
- **Fotos del PDF** (`servicios/fotos_pdf.py`): al subir la cotización se extrae la foto original de cada partida (columna FOTOGRAFÍA) y se empareja con su renglón por posición (la foto empieza ~3 pt arriba de la partida; tolerancia 15 pt). Se reduce a 1600 px, se guarda como JPEG en la biblioteca del artículo (oficial si no tenía, variante si ya tenía) y queda asignada a la partida. Las partidas fuera de catálogo reciben su foto suelta. La huella de los píxeles originales evita duplicar la misma foto entre cotizaciones. Un problema con las fotos nunca impide crear la cotización.
- **Matching** (`servicios/matching.py`): exacto por código normalizado. Con match asigna la imagen oficial; si no hay, la variante con más usos; si no hay ninguna, deja el ítem pendiente. Sin match, el ítem se guarda como `ad_hoc`.
- **Imágenes generadas** (`servicios/proveedor_imagenes.py`): la base se normaliza a PNG RGBA de máximo 1024 px; `ProveedorOpenAI` usa la edición de `gpt-image-2.5-sunburst` (con `input_fidelity="high"` sólo en la familia `gpt-image-1`, que es la única que lo acepta) y un prompt fijo (forma intacta, tres cuartos, fondo neutro, luz lateral) más la petición del vendedor. Sin `OPENAI_API_KEY` actúa `ProveedorSimulado`. Cada llamada se registra en `generaciones` y hay tope diario por usuario y global (429 con la hora de liberación).
- **PDF** (`servicios/render_pdf.py` + `plantillas/propuesta_base.html`): carta, partidas en el orden guardado con un título por sección, miniaturas incrustadas como data URI, marcador "Sin imagen", etiqueta "Render conceptual", totales (Subtotal, Flete, Montaje, IVA, Total) y leyenda al pie.
- **Presentación editorial** (`servicios/presentacion.py` + `plantillas/presentacion_editorial.html`): páginas de 810 x 1080 pt (las del ejemplo de la marca): portada con foto, manifiesto, una apertura por sección con su montaje y tres columnas de texto, las piezas (2 por página hasta 4 piezas; después rejilla de 4), cierre de ambientación, concentrado y monograma. El tamaño de cada título gigante se calcula midiendo el texto con la fuente real (fontTools) para que llene el ancho sin desbordarse. Las fotos van incrustadas como data URI.
- **Plantillas** (`routers/plantillas.py` + `servicios/ia_texto.py`): la inspiración se guarda como imagen `inspiracion` y se manda al modelo de visión, que responde un JSON con los parámetros; se filtran contra `ParametrosPlantilla` (lo que venga raro usa el valor por defecto). Sin IA se sigue sacando la paleta de la imagen con análisis local (color dominante para el papel, el más saturado para el acento).
- **Idioma y medidas** (`servicios/idiomas.py`): las etiquetas fijas de los dos PDF están en un diccionario; las medidas pasan de centímetros y metros a pies y pulgadas con reglas (el catálogo las guarda siempre en cm); los textos libres los traduce la IA una vez por cotización y quedan en caché dentro de la presentación. Si la IA no está, entra un glosario de mobiliario para que el PDF no salga a medias.
- **Moneda** (`idiomas.Dinero`): en dólares divide cada importe entre el tipo de cambio y lo dice al pie, con la fecha. Aplica igual al PDF base y a la presentación.
- **Modelo de texto**: no se escribe a mano. Se le pregunta a la cuenta de OpenAI qué modelos tiene y se toma el primero de una lista de preferencia (`ia_texto.PREFERENCIA_MODELOS`), o el que fije `OPENAI_MODELO_TEXTO`. `/api/salud` dice cuál quedó.
- **Marca** (`app/marca`, `app/fuentes`): logotipo y monograma en PNG que el render recolorea sólo a colores de marca (menta #B5FFBF, negro o crema); tipografías Bebas Neue y Public Sans empaquetadas. La paleta del vendedor sólo cambia fondo, texto y acento.
- **Montajes con IA** (`proveedor_imagenes.generar_escena`): manda hasta 6 fotos de las piezas de la sección como referencia al endpoint de edición (hasta 16 acepta el modelo) con un prompt armado con las indicaciones del vendedor, y guarda el resultado como imagen `montaje` de esa cotización. Cuenta en el mismo tope diario que las variantes y sale marcado "Render conceptual" en el PDF.
- **Flete y montaje** (`servicios/cargos.py`): al subir, una partida es cargo si su descripción dice FLETE, TRANSPORTE o TRASLADO (flete) o MONTAJE, DESMONTAJE o INSTALACIÓN (montaje), o si está en una sección llamada MONTAJE. No cuenta si la palabra viene negada ("SIN INSTALACIÓN"). El vendedor lo corrige en Revisar.
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
| PUT | `/cotizaciones/{id}/orden` | `{ids}` con las partidas en el nuevo orden de impresión |
| PATCH | `/cotizaciones/{id}/items/{item_id}/descripcion` | `{descripcion}` para esta cotización; vacío vuelve a la del sistema |
| PUT | `/cotizaciones/{id}/items/{item_id}/cargo` | `{cargo}`: `"flete"`, `"montaje"` o `null` (partida) |
| POST | `/cotizaciones/{id}/generar` | Renderiza el PDF, lo guarda en `exports`, registra el histórico y devuelve URL firmada |
| GET | `/cotizaciones/{id}/pdfs` | Historial de PDF generados (base y editorial), más reciente primero; URL para ver y para descargar |
| GET | `/perfil/yo` | Perfil del usuario autenticado |
| GET/POST | `/catalogo/items` | Búsqueda con precios e imagen oficial / alta por formulario |
| GET/PATCH | `/catalogo/items/{id}` | Detalle / edición parcial (`precios` reemplaza el conjunto) |
| POST | `/catalogo/items/carga-texto` | `{texto}` con una línea por ítem; upsert por código sin borrar datos existentes |
| GET | `/catalogo/items/{id}/imagenes` | Imágenes del ítem: oficial primero, luego por usos |
| GET/POST | `/catalogo/listas-precios` | Listas de precios |
| PATCH | `/catalogo/listas-precios/{id}` | Renombrar, ordenar o desactivar |
| GET | `/cotizaciones/{id}/presentacion` | Configuración de la presentación (o la de por defecto) y secciones actuales |
| PUT | `/cotizaciones/{id}/presentacion` | Guarda indicaciones, portada, paleta, precios, textos y secciones |
| PUT | `/cotizaciones/{id}/presentacion/imagenes` | `{hueco, imagen_id}`: portada, manifiesto, cierre o `montaje:<sección>` |
| POST | `/cotizaciones/{id}/presentacion/montajes` | `{clave, indicaciones}` → genera el montaje de esa sección con IA |
| POST | `/cotizaciones/{id}/presentacion/pdf` | Renderiza la presentación editorial y devuelve URL firmada |
| POST | `/cotizaciones/{id}/presentacion/traducir` | Traduce con IA los textos de la cotización y guarda el resultado |
| GET/POST | `/plantillas` | Plantillas del equipo / crea una desde una inspiración (multipart `archivo`) |
| PATCH/DELETE | `/plantillas/{id}` | Renombrar o ajustar parámetros / borrar con sus inspiraciones |
| POST/DELETE | `/plantillas/{id}/inspiraciones[/{imagen_id}]` | Sumar o quitar imágenes de referencia |
| POST | `/plantillas/{id}/analizar` | Vuelve a leer la inspiración con IA |
| GET/POST | `/paletas` | Paletas de la app y del equipo / guardar una nueva |
| PATCH/DELETE | `/paletas/{id}` | Editar o borrar una paleta guardada |
| GET | `/imagenes/ambientacion` | Biblioteca de fotos de ambientación |
| POST | `/imagenes` | multipart `archivo` (+ `item_id`, `etiquetas`, `tipo`: oficial, variante o ambientacion) |
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
- **`gpt-image-2.5-sunburst` con `quality=medium`** por defecto. Verificado con la cuenta real el 21/09/2026: el modelo acepta la edición con imagen base, tarda ~15 s por imagen en calidad baja y rechaza `input_fidelity`; por eso ese parámetro sólo se manda a `gpt-image-1*`.
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
- **La categoría (sección) del PDF se guarda en cada partida**; importe y costo de reposición se leen pero todavía no se guardan: sirven para validar la suma.
- **Secciones = tramos consecutivos de la misma categoría** en el orden guardado. Una partida no se puede arrastrar a otra sección (cambiaría su título); si se necesita, se mueve la sección completa.
- **El orden se guarda con una función en la base** (`reordenar_cotizacion`, migración 0008) que reescribe `orden` en una sola sentencia. Las partidas que no vengan en la lista conservan su orden relativo y van al final.
- **Varias líneas de flete (o de montaje) se suman en un solo renglón** "Flete" o "Montaje". Si no hay, el renglón no aparece.
- **El IVA se copia del PDF del sistema**, no se calcula: si el documento trae "IVA $…" se muestra ese monto y se suma al total. Si no lo trae, el total dice "(más IVA)". Cambiar una partida a flete no altera el IVA, porque es el que imprimió el sistema.
- **Los cargos no cuentan como pendientes** ni en el número de ítems, y no se les busca imagen para el PDF.
- **Las ediciones de una cotización no se pisan entre sí**: si el vendedor cambia el tipo mientras se guarda un orden, sólo la última respuesta se aplica y la pantalla vuelve a leer la cotización.
- **Catálogo real cargado desde el reporte de existencias del 18/09/2026**: 792 artículos (708 con código, 84 provisionales, 8 internos inactivos), 709 con costo de reposición, 736 precios en la lista "Precio 1", 157 con medidas. El catálogo de ejemplo quedó desactivado. Los PDFs de inventario no están en el repo.
- **La columna "PRECIO 1.00" va a la lista "Precio 1"**, no a "Público": no coincide con lo que se cotiza (la mesa 1040 está a $1,103 en el inventario y a $1,050 en la cotización 12066).
- **REPO $0.00 y la pareja REPO/PRECIO en $1.00 se tratan como sin dato**; un PRECIO de $0.00 sí se guarda (hay artículos que van incluidos, como las fundas).
- **Medidas con las etiquetas del reporte** ("ancho · largo · alto" en mesas; "respaldo · base respaldo · asiento" en sillas y bancos), sin reinterpretarlas.
- **Códigos con punto y guion pegado** ("2008.5 - SILLA", "7029-TAPETE") se reconocen en inventario y cotizaciones.
- **Las fotos del PDF entran a la biblioteca sin revisión**: la primera que llega de un artículo sin foto queda como oficial. Se puede reemplazar desde Catálogo; las siguientes cotizaciones sólo agregan variantes si traen una foto distinta.
- **Huella sobre los píxeles originales** (no sobre el JPEG), para que no cambie si se ajusta la compresión.
- **Modo oscuro con variables CSS**: los tokens de Tailwind son canales RGB en `src/index.css` (`:root` y `:root.dark`) para que el resto de la interfaz no cambie y la opacidad (`bg-fondo/60`) siga funcionando. La paleta oscura cumple contraste mínimo 4.5:1 en todos los pares de texto. El velo de las ventanas emergentes tiene su propio token (`velo`) porque con el color de texto quedaría claro. Un script en `index.html` aplica el tema antes de pintar para evitar el destello claro.
- **La presentación editorial guarda su configuración como un jsonb** (`presentaciones.config`, migración 0009) que valida Pydantic (`ConfigPresentacion`): mientras el diseño se pule, cambiar un campo no cuesta una migración.
- **La cotización manda sobre la presentación**: las secciones salen siempre de las partidas; lo guardado sólo aporta título, texto e incluir/excluir. Una sección que ya no existe se ignora y una nueva aparece con su título por defecto.
- **Dos tipos nuevos de imagen**: `ambientacion` (la sube el vendedor y queda en una biblioteca compartida) y `montaje` (render generado con IA para una cotización). Ninguno se sugiere para las partidas: el matching sigue usando sólo `oficial` y `variante`.
- **Los montajes con IA se generan a petición, de uno en uno**, no al abrir la pantalla: cada llamada cuesta dinero y cupo. "Generar los que faltan" los encadena. Al reemplazar un montaje generado, el anterior se borra de Storage.
- **Ocultar precios afecta también al concentrado**: quedan las secciones, sus partidas y sus piezas, el total de piezas y, si la cotización los trae, una línea que dice que la propuesta considera flete y montaje.
- **El concentrado lista todas las secciones**, incluso las que el vendedor excluyó de las páginas, para que la suma cuadre con el total de la cotización.
- **Everett no está en el repo**: es una tipografía con licencia comercial y no venía con los archivos de marca. El render usa Public Sans (la misma que trae la presentación de ejemplo) y toma Everett automáticamente si se colocan sus archivos en `backend/app/fuentes/marca/Everett-Regular.otf` (Light y Medium opcionales).
- **Historial de PDF en tabla propia** (`cotizacion_pdfs`, migración 0010) en vez de listar el bucket: cada generación (base o editorial) queda registrada con su tipo y fecha, así Propuestas no depende de parsear rutas de Storage y sobrevive a que cambie el esquema de carpetas. Se borra en cascada con la cotización.
- **Dos URLs firmadas por PDF**: una para ver/imprimir (`Content-Disposition` por defecto, se abre en el visor del navegador) y otra con `download=true` que fuerza "Guardar como" con el nombre que ya tiene en Storage. `Storage.urls_firmadas` gana un parámetro `descarga` en vez de duplicar el método.
- **`estado` de la cotización sigue siendo un solo valor** (`revision`/`generada`): se pone en `generada` con el primer PDF de cualquier tipo, sin importar si después se generan más. El detalle de cuántos y de qué tipo vive en `/cotizaciones/{id}/pdfs`.
- **La inspiración no genera la diagramación, la parametriza** (migración 0011): la IA responde un JSON acotado (composición, paleta, tipografía, escala de títulos, fotos a sangre, piezas por página) y el PDF lo arma la plantilla de siempre. Así cada propuesta puede verse distinta sin que el resultado sea impredecible ni se salga de la marca.
- **Aplicar una plantilla copia sus parámetros a la cotización**, no la referencia: cambiar la plantilla después no altera propuestas ya armadas. `plantilla_id` sólo se guarda para saber de dónde salieron y para mandar sus inspiraciones como referencia de estilo al generar montajes.
- **Las paletas viven en el backend** (doce de la app en el código, las del equipo en la tabla `paletas`), no duplicadas en el frontend: una sola fuente para el PDF y para la interfaz.
- **Las medidas se convierten con reglas, no con IA**: el catálogo las guarda en centímetros y las descripciones del sistema mezclan centímetros y metros, a veces sin unidad ("REDONDA DE 1.80"). Un decimal suelto entre 0.2 y 20 se toma como metros: es lo que usa este catálogo.
- **La traducción se paga una vez por texto**: queda en `presentaciones.config.traducciones` y se reutiliza. Lo que el vendedor escribió a mano en Revisar se imprime tal cual, sin traducir ni convertir, porque es una corrección deliberada.
- **La moneda y el idioma viven en la presentación y los usan los dos PDF**: así el cliente extranjero no recibe la propuesta base en pesos y español y la editorial en dólares e inglés.
- **En dólares el tipo de cambio es obligatorio** (lo valida el modelo): sin él no se inventa una conversión, se rechaza el guardado.
- **Configuraciones guardadas antes de las plantillas se migran al vuelo** (`presentacion.migrar_config`): la paleta y la tipografía sueltas pasan a `parametros` sin perder textos ni imágenes.
- **Codificación UTF-8 con finales de línea LF** (`.gitattributes`).

## Pendientes conocidos

- Probar con más exports reales del sistema (el formato se validó con la cotización 12066: 15 de 16 partidas se reconocen en el catálogo).
- 84 artículos del inventario no tienen código en el sistema (van con código provisional `SC-…`); en las cotizaciones salen como fuera de catálogo hasta que tengan código real.
- Revisar medidas dudosas del reporte físico, por ejemplo la 1046 trae largo 24 cm (¿244?). Las filas 3010 y 3200 del reporte de mesas periqueras venían dañadas y se omitieron.
- El catálogo no tiene forma de cambiar cuál foto es la oficial desde la interfaz (sólo subir una si no hay). Hace falta para corregir una foto oficial que llegó de un PDF.
- Identidad de marca en `propuesta_base.html` (el PDF base sigue siendo neutro; la marca está en la presentación editorial).
- Faltan los archivos de la tipografía Everett (ver Decisiones) y recortar el fondo de las fotos de las piezas: sobre fondo crema se nota el recuadro blanco de la foto original.
- La biblioteca de ambientación todavía no se puede depurar desde la interfaz (no hay borrar).
- La traducción y la lectura de inspiraciones dependen del modelo de texto de OpenAI; el glosario y el análisis local de color son el respaldo, pero dan menos calidad. `/estado` dice si la IA está disponible.
- Las páginas de piezas usan posiciones fijas: si una sección tiene menos piezas que las que pide la plantilla, la última página queda con espacio libre.
- Sólo hay inglés. Para otro idioma hay que sumar su diccionario de etiquetas en `servicios/idiomas.py`.
- Las cotizaciones subidas antes de la migración 0008 no tienen sección guardada: se ven sin títulos de sección (se reordenan partida por partida) y sin cargos detectados (se pueden marcar a mano).
- Paginación en la lista de propuestas si crece mucho (hoy las últimas 100).
