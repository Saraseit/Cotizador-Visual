# Despliegue en detalle

El README trae la versión corta ("Deploy en 5 pasos"). Aquí está todo lo demás: qué hace cada archivo, todas las variables, qué revisar después y cómo actualizar.

## Qué automatiza el repo

| Archivo | Para qué |
|---|---|
| `backend/Dockerfile` | Imagen Python 3.12 con Pango, Cairo, HarfBuzz, DejaVu e IBM Plex Sans (copiada desde `backend/app/fuentes`, licencia OFL) para WeasyPrint. El contexto de build es la raíz del repo. Escucha en `$PORT`. |
| `frontend/vercel.json` | Rewrite de todas las rutas a `index.html` para React Router. Vercel detecta Vite solo cuando el Root Directory es `frontend`. |
| `.github/workflows/ci.yml` | En cada push y PR corre `pytest` (con las librerías de WeasyPrint), el build del frontend y el build de la imagen Docker con una prueba de render de PDF. No despliega. |

### Por qué no hay `railway.toml` ni `vercel.json` en la raíz

- Railway deprecó *Config as Code* (`railway.json` / `railway.toml`): según su documentación, los archivos existentes sólo siguen funcionando en servicios antiguos hasta el 1 de diciembre de 2026, y un servicio nuevo los ignora (arranca con el builder Railpack). Su reemplazo, *Infrastructure as Code* (`.railway/railway.ts`), no se lee en el deploy: sólo se aplica con `railway config apply` desde la CLI, así que no ahorra el paso manual. Por eso el builder, la ruta del Dockerfile, el healthcheck y la política de reinicio se fijan una vez en el panel del servicio.
- Vercel sólo acepta el *Root Directory* como ajuste del proyecto, no desde archivo. Con Root Directory = `frontend` lee `frontend/vercel.json` y detecta Vite. Un `vercel.json` en la raíz con `cd frontend && npm ci` falla en cuanto el Root Directory es `frontend` (el comando corre ya dentro de esa carpeta).

### Configuración del servicio en Railway (panel)

| Campo | Valor |
|---|---|
| Settings → Build → Builder | `Dockerfile` |
| Settings → Build → Dockerfile Path | `backend/Dockerfile` |
| Settings → Build → Root Directory | vacío (raíz del repo) |
| Settings → Deploy → Healthcheck Path | `/api/salud` |
| Settings → Deploy → Restart Policy | `On failure` |
| Settings → Networking | *Generate Domain* |
| `INDISPENSABLE.env.example` | Las únicas variables sin valor por defecto. |
| `backend/scripts/arrancar.py` | Todo lo que se hace una sola vez después del primer deploy. |

## Variables

### Backend (Railway → servicio → Variables)

Obligatorias:

| Variable | Dónde se consigue |
|---|---|
| `SUPABASE_URL` | Supabase → Project Settings → API → Project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase → Project Settings → API Keys → `service_role` |

Recomendadas:

| Variable | Valor | Efecto si falta |
|---|---|---|
| `OPENAI_API_KEY` | platform.openai.com → API keys | Vacía: el proveedor de imágenes cae a `simulado` (sin costo) y `/api/salud` lo indica. El backend arranca igual. |

Opcionales (valor por defecto entre paréntesis, ver `.env.example` para el resto):

| Variable | Valor por defecto | Notas |
|---|---|---|
| `ENTORNO` | `desarrollo` | En `desarrollo` CORS acepta `localhost:5173` y cualquier `https://*.vercel.app`. En `produccion` exige `CORS_ORIGENES` y el backend no arranca sin ella. |
| `CORS_ORIGENES` | vacía | Dominios permitidos separados por coma, p. ej. `https://cotizador.vercel.app`. |
| `PROVEEDOR_IMAGENES` | `openai` | `simulado` para no llamar nunca a OpenAI. |
| `OPENAI_CALIDAD_IMAGENES` | `medium` | `low` abarata, `high` encarece. |
| `LIMITE_GENERACIONES_DIARIAS_USUARIO` | `20` | Llamadas al proveedor por usuario en 24 h. |
| `LIMITE_GENERACIONES_DIARIAS_GLOBAL` | `100` | Llamadas al proveedor de todo el equipo en 24 h. |
| `SUPABASE_JWT_SECRET` | vacía | Sólo si el proyecto firma con HS256 (Project Settings → JWT Keys → Legacy JWT Secret). Los proyectos nuevos usan ES256 y no la necesitan. |
| `PORT` | la inyecta Railway | No definirla a mano. |

### Frontend (Vercel → proyecto → Settings → Environment Variables)

| Variable | Dónde se consigue |
|---|---|
| `VITE_SUPABASE_URL` | mismo valor que `SUPABASE_URL` |
| `VITE_SUPABASE_ANON_KEY` | Supabase → Project Settings → API Keys → `anon` / publishable |
| `VITE_API_URL` | dominio público del backend en Railway (Settings → Networking → Generate Domain), sin barra final |

Cambiar una `VITE_*` requiere volver a desplegar el frontend (Vercel las incrusta en el build).

## Después del primer deploy

1. Corre `python backend/scripts/arrancar.py` desde tu máquina (necesita `pip install -e ./backend`). Hace, en orden e idempotente:
   - pide y guarda en `.env` las variables que falten;
   - compara `supabase/migrations/` con lo aplicado (lee `supabase_migrations.schema_migrations` a través de la función `migraciones_aplicadas`). Para aplicar pendientes desde el script necesita `SUPABASE_DB_URL` (Supabase → Connect → Session pooler, con tu contraseña de base); si no la das, lista los archivos para pegarlos en el SQL Editor;
   - crea el primer admin (si ya existe uno, sólo ofrece crear otro);
   - siembra el catálogo de ejemplo si dices que sí;
   - llama a `/api/salud` del backend desplegado y muestra el diagnóstico;
   - resume qué quedó listo.
2. Abre el frontend, entra con el admin y ve a **Estado**: todos los círculos deben estar en verde. Si alguno está en rojo, el detalle dice qué falta.
3. Llena `backend/fixtures/catalogo_plantilla.csv` con el catálogo real, pon las fotos en una carpeta nombradas por código y corre `scripts/cargar_catalogo.py` (ver README, "Seeding del catálogo").
4. Cuando tengas un export real del sistema, ajusta `backend/fixtures/mapeo_columnas.json` (hoja, fila de encabezados, columnas, celdas de cliente y referencia; para PDF, `pdf.estrategia`).
5. Para pasar a producción: en Railway pon `ENTORNO=produccion` y `CORS_ORIGENES=https://<tu-dominio>.vercel.app`, y en Supabase activa *Authentication → Password security → Leaked password protection* (aviso del linter que sólo se cambia desde el dashboard).

## Actualizar

- Cada push a `main` dispara CI (pytest + build). Railway y Vercel despliegan `main` automáticamente si dejaste activado el auto-deploy al conectar el repo (es el valor por defecto en ambos).
- Migraciones nuevas: agrégalas a `supabase/migrations/` con el prefijo de fecha y vuelve a correr `arrancar.py` (o aplícalas en el SQL Editor). El script sólo aplica las que falten.
- Un cambio de esquema que rompa compatibilidad se despliega primero en Supabase y después en Railway.

## Probar la imagen en local

```bash
docker build -f backend/Dockerfile -t cotizador-backend .
docker run --rm -p 8000:8000 --env-file .env cotizador-backend
curl http://localhost:8000/api/salud
```

## Ajustes manuales que no se pudieron eliminar

- **Builder, ruta del Dockerfile, healthcheck y política de reinicio en Railway**: Config as Code está deprecado y su reemplazo requiere la CLI (ver arriba). Son cuatro campos del panel, una sola vez.
- **Root Directory = `frontend` en Vercel**: no se acepta desde archivo.
- **Generar el dominio público en Railway** (Settings → Networking → Generate Domain): Railway no lo crea solo y `VITE_API_URL` depende de él.
- **Protección de contraseñas filtradas en Supabase Auth**: es un interruptor del dashboard; el linter lo marca como WARN mientras esté apagado.
- **`SUPABASE_DB_URL` para que `arrancar.py` aplique migraciones**: Supabase no expone la contraseña de la base por API; si no la pegas, las migraciones se aplican desde el SQL Editor (o con `supabase db push`).
