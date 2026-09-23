-- ============================================================================
-- Plantillas de presentación, paletas guardadas y descripción editable.
--   - plantillas: cada una nace de una inspiración que sube el vendedor. La IA propone paleta,
--     tipografía y parámetros de composición; quedan en `config` (jsonb que valida Pydantic) para
--     poder pulir el diseño sin migrar. Las imágenes de inspiración se guardan como
--     `imagenes.tipo = 'inspiracion'` y sus ids viven en config.inspiraciones.
--   - paletas: las que el equipo guarda además de las predefinidas del código.
--   - cotizacion_items.descripcion_editada: texto que el vendedor ajusta en Revisar para esa
--     cotización. No toca el catálogo ni el sistema de la empresa; si está lleno, es lo que se
--     imprime (y no se manda a traducir, porque es una corrección deliberada).
--   - Sólo escribe el backend (service_role); los autenticados pueden leer.
-- ============================================================================

alter table public.imagenes drop constraint imagenes_tipo_check;
alter table public.imagenes add constraint imagenes_tipo_check
  check (tipo in ('oficial', 'variante', 'generada', 'ambientacion', 'montaje', 'inspiracion'));

alter table public.cotizacion_items
  add column descripcion_editada text not null default '';

create table public.plantillas (
  id              uuid primary key default gen_random_uuid(),
  nombre          text not null,
  descripcion     text not null default '',
  config          jsonb not null default '{}'::jsonb,
  creado_por      uuid references public.perfiles (id) on delete set null,
  creado_en       timestamptz not null default now(),
  actualizado_en  timestamptz not null default now()
);

create index plantillas_creado_idx on public.plantillas (creado_en desc);
create index plantillas_creado_por_idx on public.plantillas (creado_por);

create trigger plantillas_tocar
  before update on public.plantillas
  for each row execute function public.tocar_actualizado_en();

create table public.paletas (
  id          uuid primary key default gen_random_uuid(),
  nombre      text not null,
  fondo       text not null,
  texto       text not null,
  acento      text not null,
  creado_por  uuid references public.perfiles (id) on delete set null,
  creado_en   timestamptz not null default now()
);

create index paletas_creado_idx on public.paletas (creado_en desc);
create index paletas_creado_por_idx on public.paletas (creado_por);

alter table public.plantillas enable row level security;
alter table public.paletas enable row level security;

create policy "plantillas: leer autenticados"
  on public.plantillas for select to authenticated using (true);

create policy "paletas: leer autenticados"
  on public.paletas for select to authenticated using (true);
-- Sin políticas de escritura: sólo service_role (que ignora RLS) escribe.
