-- ============================================================================
-- Presentación editorial (piloto).
--   - presentaciones: una configuración por cotización (indicaciones del vendedor, portada, paleta,
--     mostrar precios, textos por sección y qué imagen va en cada hueco). Es un jsonb que valida el
--     backend (ConfigPresentacion), para poder pulir el diseño sin migrar cada cambio.
--   - imagenes.tipo suma dos valores:
--       'ambientacion': fotos de ambiente y montajes que sube el vendedor; forman una biblioteca
--                       compartida que se reutiliza entre presentaciones.
--       'montaje':      renders de montaje generados con IA para una presentación.
--     Ninguno se sugiere para las partidas: el matching sólo usa 'oficial' y 'variante'.
-- ============================================================================

alter table public.imagenes drop constraint imagenes_tipo_check;
alter table public.imagenes add constraint imagenes_tipo_check
  check (tipo in ('oficial', 'variante', 'generada', 'ambientacion', 'montaje'));

create index imagenes_tipo_creado_idx on public.imagenes (tipo, creado_en desc);

create table public.presentaciones (
  cotizacion_id   uuid primary key references public.cotizaciones (id) on delete cascade,
  config          jsonb not null default '{}'::jsonb,
  actualizado_por uuid references public.perfiles (id) on delete set null,
  creado_en       timestamptz not null default now(),
  actualizado_en  timestamptz not null default now()
);

create index presentaciones_actualizado_por_idx on public.presentaciones (actualizado_por);

create trigger presentaciones_tocar
  before update on public.presentaciones
  for each row execute function public.tocar_actualizado_en();

-- Mismas reglas que cotizacion_items: todos leen; escribe el dueño de la cotización o un admin.
-- El backend usa la service role y aplica estas reglas en código.
alter table public.presentaciones enable row level security;

create policy "presentaciones: leer todas"
  on public.presentaciones for select to authenticated using (true);

create policy "presentaciones: insertar si la cotizacion es propia o admin"
  on public.presentaciones for insert to authenticated
  with check (
    exists (
      select 1 from public.cotizaciones c
      where c.id = cotizacion_id and (c.creado_por = (select auth.uid()) or public.es_admin())
    )
  );

create policy "presentaciones: actualizar si la cotizacion es propia o admin"
  on public.presentaciones for update to authenticated
  using (
    exists (
      select 1 from public.cotizaciones c
      where c.id = cotizacion_id and (c.creado_por = (select auth.uid()) or public.es_admin())
    )
  )
  with check (
    exists (
      select 1 from public.cotizaciones c
      where c.id = cotizacion_id and (c.creado_por = (select auth.uid()) or public.es_admin())
    )
  );

create policy "presentaciones: borrar si la cotizacion es propia o admin"
  on public.presentaciones for delete to authenticated
  using (
    exists (
      select 1 from public.cotizaciones c
      where c.id = cotizacion_id and (c.creado_por = (select auth.uid()) or public.es_admin())
    )
  );
