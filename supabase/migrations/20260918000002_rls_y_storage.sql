-- ============================================================================
-- Políticas RLS y buckets de Storage
--
-- Reglas:
--   - Usuarios autenticados leen todo.
--   - cotizaciones / cotizacion_items: solo escribe el dueño (o un admin).
--   - catalogo_items / imagenes: biblioteca compartida, escribe cualquier autenticado.
--   - perfiles: solo escribe su dueño.
--
-- El backend usa la service role key (que ignora RLS) y aplica estas mismas
-- reglas en código. Las políticas protegen el acceso directo con la anon key.
-- ============================================================================

alter table public.perfiles         enable row level security;
alter table public.catalogo_items   enable row level security;
alter table public.imagenes         enable row level security;
alter table public.cotizaciones     enable row level security;
alter table public.cotizacion_items enable row level security;

-- perfiles ------------------------------------------------------------------
create policy "perfiles: leer todos"
  on public.perfiles for select to authenticated using (true);

create policy "perfiles: crear el propio"
  on public.perfiles for insert to authenticated with check (id = auth.uid());

create policy "perfiles: editar el propio"
  on public.perfiles for update to authenticated
  using (id = auth.uid()) with check (id = auth.uid());

-- catalogo_items (biblioteca compartida) ------------------------------------
create policy "catalogo: leer todos"
  on public.catalogo_items for select to authenticated using (true);

create policy "catalogo: escribir autenticados"
  on public.catalogo_items for all to authenticated
  using (true) with check (true);

-- imagenes (biblioteca compartida) ------------------------------------------
create policy "imagenes: leer todas"
  on public.imagenes for select to authenticated using (true);

create policy "imagenes: escribir autenticados"
  on public.imagenes for all to authenticated
  using (true) with check (true);

-- cotizaciones ---------------------------------------------------------------
create policy "cotizaciones: leer todas"
  on public.cotizaciones for select to authenticated using (true);

create policy "cotizaciones: crear propias"
  on public.cotizaciones for insert to authenticated
  with check (creado_por = auth.uid());

create policy "cotizaciones: editar propias o admin"
  on public.cotizaciones for update to authenticated
  using (creado_por = auth.uid() or public.es_admin())
  with check (creado_por = auth.uid() or public.es_admin());

create policy "cotizaciones: borrar propias o admin"
  on public.cotizaciones for delete to authenticated
  using (creado_por = auth.uid() or public.es_admin());

-- cotizacion_items -----------------------------------------------------------
create policy "cotizacion_items: leer todos"
  on public.cotizacion_items for select to authenticated using (true);

create policy "cotizacion_items: escribir si la cotizacion es propia o admin"
  on public.cotizacion_items for all to authenticated
  using (
    exists (
      select 1 from public.cotizaciones c
      where c.id = cotizacion_id and (c.creado_por = auth.uid() or public.es_admin())
    )
  )
  with check (
    exists (
      select 1 from public.cotizaciones c
      where c.id = cotizacion_id and (c.creado_por = auth.uid() or public.es_admin())
    )
  );

-- Storage: dos buckets privados ---------------------------------------------
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values
  ('imagenes', 'imagenes', false, 15728640, array['image/png', 'image/jpeg', 'image/webp']),
  ('exports',  'exports',  false, 26214400, null)
on conflict (id) do nothing;

-- Las imágenes las puede leer y subir cualquier autenticado (biblioteca compartida).
-- Los exports y PDFs solo los maneja el backend con la service role.
create policy "storage imagenes: leer autenticados"
  on storage.objects for select to authenticated
  using (bucket_id = 'imagenes');

create policy "storage imagenes: subir autenticados"
  on storage.objects for insert to authenticated
  with check (bucket_id = 'imagenes');
