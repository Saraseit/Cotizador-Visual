-- ============================================================================
-- Registro de generaciones con IA, para aplicar topes diarios por usuario y globales.
-- Cada fila es una llamada al proveedor (aunque produzca varias imágenes).
-- Sólo escribe el backend (service_role); los autenticados pueden leer.
-- ============================================================================

create table public.generaciones (
  id             uuid primary key default gen_random_uuid(),
  usuario_id     uuid not null references public.perfiles (id) on delete cascade,
  cotizacion_id  uuid references public.cotizaciones (id) on delete set null,
  imagen_base_id uuid references public.imagenes (id) on delete set null,
  peticion       text not null default '',
  proveedor      text not null default '',
  modelo         text not null default '',
  cantidad       integer not null default 1,
  creado_en      timestamptz not null default now()
);

create index generaciones_usuario_creado_idx on public.generaciones (usuario_id, creado_en desc);
create index generaciones_creado_idx on public.generaciones (creado_en desc);
create index generaciones_cotizacion_idx on public.generaciones (cotizacion_id);
create index generaciones_imagen_base_idx on public.generaciones (imagen_base_id);

alter table public.generaciones enable row level security;

create policy "generaciones: leer autenticados"
  on public.generaciones for select to authenticated using (true);
-- Sin políticas de escritura: sólo service_role (que ignora RLS) inserta.

-- El resumen de biblioteca incluye las generaciones de las últimas 24 h.
create or replace function public.resumen_biblioteca(limite_sin_imagen integer default 20)
returns jsonb
language sql
stable
security definer
set search_path = public
as $$
  with activos as (
    select id, codigo, nombre, categoria from public.catalogo_items where activo
  ),
  con_oficial as (
    select distinct item_id from public.imagenes where tipo = 'oficial' and item_id is not null
  ),
  con_alguna as (
    select distinct item_id from public.imagenes where item_id is not null
  ),
  veces_cotizados as (
    select item_id, count(*)::int as veces
    from public.cotizacion_items
    where item_id is not null
    group by item_id
  ),
  sin_imagen as (
    select a.id, a.codigo, a.nombre, a.categoria, coalesce(v.veces, 0) as veces_cotizado
    from activos a
    left join con_alguna c on c.item_id = a.id
    left join veces_cotizados v on v.item_id = a.id
    where c.item_id is null
    order by veces_cotizado desc, a.codigo
    limit limite_sin_imagen
  )
  select jsonb_build_object(
    'items_activos',          (select count(*) from activos),
    'items_con_oficial',      (select count(*) from activos a join con_oficial c on c.item_id = a.id),
    'porcentaje_con_oficial', case
                                when (select count(*) from activos) = 0 then 0
                                else round(
                                  100.0 * (select count(*) from activos a join con_oficial c on c.item_id = a.id)
                                  / (select count(*) from activos), 1)
                              end,
    'total_variantes',        (select count(*) from public.imagenes where tipo = 'variante'),
    'total_generadas',        (select count(*) from public.imagenes where tipo = 'generada'),
    'total_generaciones_24h', (select count(*) from public.generaciones where creado_en > now() - interval '24 hours'),
    'total_sin_imagen',       (select count(*) from activos a left join con_alguna c on c.item_id = a.id where c.item_id is null),
    'items_sin_imagen',       (select coalesce(jsonb_agg(to_jsonb(s)), '[]'::jsonb) from sin_imagen s)
  );
$$;
