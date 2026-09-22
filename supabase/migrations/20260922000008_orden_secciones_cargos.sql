-- ============================================================================
-- Orden por secciones, cargos (flete / montaje) e IVA del documento.
--   - cotizacion_items.categoria: sección del PDF del sistema (SILLAS, MESA BANQUETE…); '' si no tiene.
--   - cotizacion_items.cargo: 'flete' | 'montaje' si la partida no es mobiliario sino un cargo que se
--     muestra abajo, junto al subtotal; null en las partidas normales.
--   - cotizaciones.iva_documento: IVA impreso en el PDF del sistema; null si el PDF sólo dice "más IVA".
--   - reordenar_cotizacion(): guarda en una sola operación el orden que el vendedor arma arrastrando.
-- ============================================================================

alter table public.cotizacion_items
  add column categoria text not null default '',
  add column cargo text check (cargo in ('flete', 'montaje'));

alter table public.cotizaciones
  add column iva_documento numeric(14, 2);

-- Reasigna `orden` según la posición de cada id en `ids`. Los ítems de la cotización que no vengan en
-- la lista conservan su orden relativo y quedan al final. Sólo la llama el backend (service_role),
-- que antes verifica que el usuario pueda editar la cotización.
create or replace function public.reordenar_cotizacion(p_cotizacion uuid, p_ids uuid[])
returns integer
language sql
security definer
set search_path = public
as $$
  with nuevos as (
    select ci.id,
           row_number() over (
             order by coalesce(array_position(p_ids, ci.id), 2147483647), ci.orden, ci.creado_en
           ) - 1 as nuevo_orden
    from public.cotizacion_items ci
    where ci.cotizacion_id = p_cotizacion
  ),
  actualizados as (
    update public.cotizacion_items ci
    set orden = n.nuevo_orden
    from nuevos n
    where ci.id = n.id and ci.orden is distinct from n.nuevo_orden
    returning 1
  )
  select count(*)::integer from actualizados;
$$;

revoke execute on function public.reordenar_cotizacion(uuid, uuid[]) from public, anon, authenticated;
grant execute on function public.reordenar_cotizacion(uuid, uuid[]) to service_role;
