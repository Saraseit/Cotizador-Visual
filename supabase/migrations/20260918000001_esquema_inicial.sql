-- ============================================================================
-- Cotizador visual — esquema inicial
-- Tablas: perfiles, catalogo_items, imagenes, cotizaciones, cotizacion_items
-- Todas con id uuid, creado_en y actualizado_en.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Utilidades
-- ---------------------------------------------------------------------------

-- Mantiene actualizado_en al día en cualquier UPDATE.
create or replace function public.tocar_actualizado_en()
returns trigger
language plpgsql
as $$
begin
  new.actualizado_en = now();
  return new;
end;
$$;

-- ---------------------------------------------------------------------------
-- perfiles (1:1 con auth.users)
-- ---------------------------------------------------------------------------
create table public.perfiles (
  id             uuid primary key references auth.users (id) on delete cascade,
  nombre         text not null default '',
  rol            text not null default 'vendedor' check (rol in ('vendedor', 'admin')),
  creado_en      timestamptz not null default now(),
  actualizado_en timestamptz not null default now()
);

create trigger perfiles_tocar
  before update on public.perfiles
  for each row execute function public.tocar_actualizado_en();

-- Devuelve true si el usuario autenticado es admin. SECURITY DEFINER para
-- poder consultarse desde políticas RLS sin recursión.
create or replace function public.es_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select coalesce(
    (select rol = 'admin' from public.perfiles where id = auth.uid()),
    false
  );
$$;

-- ---------------------------------------------------------------------------
-- catalogo_items
-- ---------------------------------------------------------------------------
create table public.catalogo_items (
  id             uuid primary key default gen_random_uuid(),
  codigo         text not null unique,
  nombre         text not null,
  categoria      text not null default '',
  activo         boolean not null default true,
  creado_en      timestamptz not null default now(),
  actualizado_en timestamptz not null default now()
);

create trigger catalogo_items_tocar
  before update on public.catalogo_items
  for each row execute function public.tocar_actualizado_en();

-- ---------------------------------------------------------------------------
-- imagenes (biblioteca compartida)
-- ---------------------------------------------------------------------------
create table public.imagenes (
  id             uuid primary key default gen_random_uuid(),
  item_id        uuid references public.catalogo_items (id) on delete set null,
  ruta_storage   text not null,
  tipo           text not null check (tipo in ('oficial', 'variante', 'generada')),
  etiquetas      text[] not null default '{}',
  -- Para 'generada': {peticion, imagen_base_id, proveedor, modelo}
  origen         jsonb not null default '{}'::jsonb,
  subida_por     uuid references public.perfiles (id) on delete set null,
  usos           integer not null default 0,
  creado_en      timestamptz not null default now(),
  actualizado_en timestamptz not null default now()
);

create index imagenes_item_id_idx on public.imagenes (item_id);
-- Como máximo una imagen oficial por ítem.
create unique index imagenes_oficial_unica_idx
  on public.imagenes (item_id)
  where tipo = 'oficial' and item_id is not null;

create trigger imagenes_tocar
  before update on public.imagenes
  for each row execute function public.tocar_actualizado_en();

-- ---------------------------------------------------------------------------
-- cotizaciones
-- ---------------------------------------------------------------------------
create table public.cotizaciones (
  id                  uuid primary key default gen_random_uuid(),
  nombre_cliente      text not null default '',
  referencia_externa  text not null default '',
  creado_por          uuid not null references public.perfiles (id) on delete cascade,
  archivo_origen_ruta text not null default '',
  estado              text not null default 'revision' check (estado in ('revision', 'generada')),
  creado_en           timestamptz not null default now(),
  actualizado_en      timestamptz not null default now()
);

create index cotizaciones_creado_por_idx on public.cotizaciones (creado_por, creado_en desc);

create trigger cotizaciones_tocar
  before update on public.cotizaciones
  for each row execute function public.tocar_actualizado_en();

-- ---------------------------------------------------------------------------
-- cotizacion_items
-- ---------------------------------------------------------------------------
create table public.cotizacion_items (
  id                   uuid primary key default gen_random_uuid(),
  cotizacion_id        uuid not null references public.cotizaciones (id) on delete cascade,
  item_id              uuid references public.catalogo_items (id) on delete set null,
  codigo_origen        text not null default '',
  descripcion_origen   text not null default '',
  cantidad             numeric(12, 3) not null default 1,
  precio_unitario      numeric(14, 2) not null default 0,
  imagen_id            uuid references public.imagenes (id) on delete set null,
  tipo_item            text not null check (tipo_item in ('catalogo', 'ad_hoc')),
  es_render_conceptual boolean not null default false,
  orden                integer not null default 0,
  creado_en            timestamptz not null default now(),
  actualizado_en       timestamptz not null default now()
);

create index cotizacion_items_cotizacion_idx on public.cotizacion_items (cotizacion_id, orden);
create index cotizacion_items_item_idx on public.cotizacion_items (item_id);

create trigger cotizacion_items_tocar
  before update on public.cotizacion_items
  for each row execute function public.tocar_actualizado_en();

-- Reglas de negocio al asignar una imagen a un ítem de cotización:
--   1. Se incrementa imagenes.usos de la imagen asignada.
--   2. Si la imagen es 'generada', el ítem queda como render conceptual.
create or replace function public.al_asignar_imagen()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  tipo_imagen text;
begin
  if new.imagen_id is null then
    new.es_render_conceptual = false;
    return new;
  end if;

  if tg_op = 'INSERT' or new.imagen_id is distinct from old.imagen_id then
    update public.imagenes set usos = usos + 1 where id = new.imagen_id;
  end if;

  select tipo into tipo_imagen from public.imagenes where id = new.imagen_id;
  new.es_render_conceptual = (tipo_imagen = 'generada');
  return new;
end;
$$;

create trigger cotizacion_items_al_asignar_imagen
  before insert or update of imagen_id on public.cotizacion_items
  for each row execute function public.al_asignar_imagen();

-- ---------------------------------------------------------------------------
-- Resumen de biblioteca (usado por GET /api/biblioteca/resumen vía RPC)
-- ---------------------------------------------------------------------------
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
    'total_sin_imagen',       (select count(*) from activos a left join con_alguna c on c.item_id = a.id where c.item_id is null),
    'items_sin_imagen',       (select coalesce(jsonb_agg(to_jsonb(s)), '[]'::jsonb) from sin_imagen s)
  );
$$;
