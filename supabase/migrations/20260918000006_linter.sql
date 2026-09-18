-- ============================================================================
-- Ajustes que pide el linter de Supabase (seguridad y rendimiento):
--   1. resumen_biblioteca(integer) sólo la llama el backend: se revoca a authenticated.
--      es_admin() se queda ejecutable por authenticated porque la usan las políticas.
--   2. auth.uid() envuelto en (select ...) para que se evalúe una vez por consulta.
--   3. Sin políticas permisivas duplicadas: las "for all" se separan en insert/update/delete
--      y la de select queda sola.
--   4. Índices para las llaves foráneas sin cubrir.
-- ============================================================================

-- 1. Funciones ---------------------------------------------------------------
revoke execute on function public.resumen_biblioteca(integer) from authenticated;

-- 2 y 3. Políticas -------------------------------------------------------------

-- perfiles
drop policy "perfiles: crear el propio" on public.perfiles;
create policy "perfiles: crear el propio"
  on public.perfiles for insert to authenticated
  with check (id = (select auth.uid()));

drop policy "perfiles: editar el propio" on public.perfiles;
create policy "perfiles: editar el propio"
  on public.perfiles for update to authenticated
  using (id = (select auth.uid())) with check (id = (select auth.uid()));

-- catalogo_items
drop policy "catalogo: escribir autenticados" on public.catalogo_items;
create policy "catalogo: insertar autenticados"
  on public.catalogo_items for insert to authenticated with check (true);
create policy "catalogo: actualizar autenticados"
  on public.catalogo_items for update to authenticated using (true) with check (true);
create policy "catalogo: borrar autenticados"
  on public.catalogo_items for delete to authenticated using (true);

-- imagenes
drop policy "imagenes: escribir autenticados" on public.imagenes;
create policy "imagenes: insertar autenticados"
  on public.imagenes for insert to authenticated with check (true);
create policy "imagenes: actualizar autenticados"
  on public.imagenes for update to authenticated using (true) with check (true);
create policy "imagenes: borrar autenticados"
  on public.imagenes for delete to authenticated using (true);

-- listas_precios
drop policy "listas_precios: escribir autenticados" on public.listas_precios;
create policy "listas_precios: insertar autenticados"
  on public.listas_precios for insert to authenticated with check (true);
create policy "listas_precios: actualizar autenticados"
  on public.listas_precios for update to authenticated using (true) with check (true);
create policy "listas_precios: borrar autenticados"
  on public.listas_precios for delete to authenticated using (true);

-- precios_items
drop policy "precios_items: escribir autenticados" on public.precios_items;
create policy "precios_items: insertar autenticados"
  on public.precios_items for insert to authenticated with check (true);
create policy "precios_items: actualizar autenticados"
  on public.precios_items for update to authenticated using (true) with check (true);
create policy "precios_items: borrar autenticados"
  on public.precios_items for delete to authenticated using (true);

-- cotizaciones
drop policy "cotizaciones: crear propias" on public.cotizaciones;
create policy "cotizaciones: crear propias"
  on public.cotizaciones for insert to authenticated
  with check (creado_por = (select auth.uid()));

drop policy "cotizaciones: editar propias o admin" on public.cotizaciones;
create policy "cotizaciones: editar propias o admin"
  on public.cotizaciones for update to authenticated
  using (creado_por = (select auth.uid()) or (select public.es_admin()))
  with check (creado_por = (select auth.uid()) or (select public.es_admin()));

drop policy "cotizaciones: borrar propias o admin" on public.cotizaciones;
create policy "cotizaciones: borrar propias o admin"
  on public.cotizaciones for delete to authenticated
  using (creado_por = (select auth.uid()) or (select public.es_admin()));

-- cotizacion_items
drop policy "cotizacion_items: escribir si la cotizacion es propia o admin" on public.cotizacion_items;
create policy "cotizacion_items: insertar si la cotizacion es propia o admin"
  on public.cotizacion_items for insert to authenticated
  with check (
    exists (
      select 1 from public.cotizaciones c
      where c.id = cotizacion_id and (c.creado_por = (select auth.uid()) or (select public.es_admin()))
    )
  );
create policy "cotizacion_items: actualizar si la cotizacion es propia o admin"
  on public.cotizacion_items for update to authenticated
  using (
    exists (
      select 1 from public.cotizaciones c
      where c.id = cotizacion_id and (c.creado_por = (select auth.uid()) or (select public.es_admin()))
    )
  )
  with check (
    exists (
      select 1 from public.cotizaciones c
      where c.id = cotizacion_id and (c.creado_por = (select auth.uid()) or (select public.es_admin()))
    )
  );
create policy "cotizacion_items: borrar si la cotizacion es propia o admin"
  on public.cotizacion_items for delete to authenticated
  using (
    exists (
      select 1 from public.cotizaciones c
      where c.id = cotizacion_id and (c.creado_por = (select auth.uid()) or (select public.es_admin()))
    )
  );

-- 4. Índices -------------------------------------------------------------------
create index if not exists cotizacion_items_imagen_idx on public.cotizacion_items (imagen_id);
create index if not exists imagenes_subida_por_idx on public.imagenes (subida_por);
