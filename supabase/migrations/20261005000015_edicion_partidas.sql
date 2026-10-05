-- ============================================================================
-- Edición de la cotización en Revisar (cambios negociados después del PDF del sistema).
--   - cotizacion_items.origen: 'sistema' (vino en el PDF) o 'provista' (se agregó aquí).
--   - cotizacion_items.cantidad_sistema / precio_sistema / categoria_sistema: lo que dice el sistema
--     principal. Si difieren de cantidad / precio_unitario / categoria, la partida se editó aquí.
--   - cotizacion_items.eliminada: partida del sistema que se quitó en ProVista (se puede restaurar).
--   Con cualquiera de esos cambios la cotización queda "no alineada al sistema principal" hasta que
--   el vendedor marca que ya los aplicó allá: alinear_cotizacion() hace que lo de ProVista pase a ser
--   lo del sistema.
--   - cotizacion_cambios: historial de los cambios (quién, cuándo, qué).
--   - Sólo escribe el backend (service_role); los autenticados pueden leer.
-- ============================================================================

alter table public.cotizacion_items
  add column origen text not null default 'sistema' check (origen in ('sistema', 'provista')),
  add column cantidad_sistema numeric(12, 3),
  add column precio_sistema numeric(14, 2),
  add column categoria_sistema text,
  add column eliminada boolean not null default false;

update public.cotizacion_items
set cantidad_sistema = cantidad,
    precio_sistema = precio_unitario,
    categoria_sistema = categoria;

create table public.cotizacion_cambios (
  id             uuid primary key default gen_random_uuid(),
  cotizacion_id  uuid not null references public.cotizaciones (id) on delete cascade,
  usuario_id     uuid references public.perfiles (id) on delete set null,
  tipo           text not null,
  descripcion    text not null default '',
  datos          jsonb not null default '{}'::jsonb,
  creado_en      timestamptz not null default now()
);

create index cotizacion_cambios_cotizacion_idx on public.cotizacion_cambios (cotizacion_id, creado_en desc);
create index cotizacion_cambios_usuario_idx on public.cotizacion_cambios (usuario_id);

alter table public.cotizacion_cambios enable row level security;

create policy "cotizacion_cambios: leer autenticados"
  on public.cotizacion_cambios for select to authenticated using (true);
-- Sin políticas de escritura: sólo service_role (que ignora RLS) escribe.

-- Los cambios hechos en ProVista ya están en el sistema principal: lo actual pasa a ser "lo del
-- sistema" y las partidas quitadas se borran. Sólo la llama el backend, que antes verifica permisos.
create or replace function public.alinear_cotizacion(p_cotizacion uuid)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  cambiadas integer;
begin
  delete from public.cotizacion_items where cotizacion_id = p_cotizacion and eliminada;
  update public.cotizacion_items
  set origen = 'sistema',
      cantidad_sistema = cantidad,
      precio_sistema = precio_unitario,
      categoria_sistema = categoria
  where cotizacion_id = p_cotizacion;
  get diagnostics cambiadas = row_count;
  return cambiadas;
end;
$$;

revoke execute on function public.alinear_cotizacion(uuid) from public, anon, authenticated;
grant execute on function public.alinear_cotizacion(uuid) to service_role;
