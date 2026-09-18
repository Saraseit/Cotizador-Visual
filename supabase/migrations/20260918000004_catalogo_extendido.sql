-- ============================================================================
-- Catálogo extendido: descripción, medidas, etiquetas, costo de reposición y
-- varias listas de precios por ítem.
-- ============================================================================

alter table public.catalogo_items
  add column descripcion      text not null default '',
  add column medidas          text not null default '',
  add column etiquetas        text[] not null default '{}',
  add column costo_reposicion numeric(14, 2);

-- Listas de precios (Público, Distribuidor, ...). El admin las gestiona desde el front.
create table public.listas_precios (
  id             uuid primary key default gen_random_uuid(),
  nombre         text not null unique,
  orden          integer not null default 0,
  activo         boolean not null default true,
  creado_en      timestamptz not null default now(),
  actualizado_en timestamptz not null default now()
);

create trigger listas_precios_tocar
  before update on public.listas_precios
  for each row execute function public.tocar_actualizado_en();

-- Precio de un ítem en una lista.
create table public.precios_items (
  item_id        uuid not null references public.catalogo_items (id) on delete cascade,
  lista_id       uuid not null references public.listas_precios (id) on delete cascade,
  precio         numeric(14, 2) not null default 0,
  creado_en      timestamptz not null default now(),
  actualizado_en timestamptz not null default now(),
  primary key (item_id, lista_id)
);

create index precios_items_lista_idx on public.precios_items (lista_id);

create trigger precios_items_tocar
  before update on public.precios_items
  for each row execute function public.tocar_actualizado_en();

-- RLS: biblioteca compartida, igual que catalogo_items.
alter table public.listas_precios enable row level security;
alter table public.precios_items  enable row level security;

create policy "listas_precios: leer todos"
  on public.listas_precios for select to authenticated using (true);
create policy "listas_precios: escribir autenticados"
  on public.listas_precios for all to authenticated using (true) with check (true);

create policy "precios_items: leer todos"
  on public.precios_items for select to authenticated using (true);
create policy "precios_items: escribir autenticados"
  on public.precios_items for all to authenticated using (true) with check (true);

-- Dos listas de arranque; se pueden renombrar o desactivar desde el front.
insert into public.listas_precios (nombre, orden) values ('Público', 1), ('Distribuidor', 2)
on conflict (nombre) do nothing;
