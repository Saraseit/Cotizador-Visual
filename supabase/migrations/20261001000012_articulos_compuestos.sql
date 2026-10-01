-- ============================================================================
-- Artículos compuestos de una cotización.
--   - Desde Revisar el vendedor marca varias partidas (p. ej. la cubierta y la base de una mesa) y las
--     combina: en los dos PDF salen como un solo artículo, con una foto y un nombre, y debajo sus
--     componentes. Es sólo presentación: cada partida conserva su código, cantidad y precio, y los
--     importes y totales no cambian.
--   - cotizacion_compuestos.imagen_id: la foto del artículo completo. Puede ser la de uno de los
--     componentes, una que sube el vendedor o un render con IA hecho a partir de las de los
--     componentes (estas dos últimas se guardan además en la galería de cada SKU).
--   - cotizacion_items.compuesto_id: a qué compuesto pertenece la partida (null = partida suelta).
--     Al borrar el compuesto las partidas vuelven a ser sueltas.
--   - Sólo escribe el backend (service_role); los autenticados pueden leer.
-- ============================================================================

create table public.cotizacion_compuestos (
  id              uuid primary key default gen_random_uuid(),
  cotizacion_id   uuid not null references public.cotizaciones (id) on delete cascade,
  nombre          text not null default '',
  imagen_id       uuid references public.imagenes (id) on delete set null,
  creado_en       timestamptz not null default now(),
  actualizado_en  timestamptz not null default now()
);

create index cotizacion_compuestos_cotizacion_idx on public.cotizacion_compuestos (cotizacion_id);
create index cotizacion_compuestos_imagen_idx on public.cotizacion_compuestos (imagen_id);

create trigger cotizacion_compuestos_tocar
  before update on public.cotizacion_compuestos
  for each row execute function public.tocar_actualizado_en();

alter table public.cotizacion_items
  add column compuesto_id uuid references public.cotizacion_compuestos (id) on delete set null;

create index cotizacion_items_compuesto_idx on public.cotizacion_items (compuesto_id);

alter table public.cotizacion_compuestos enable row level security;

create policy "cotizacion_compuestos: leer autenticados"
  on public.cotizacion_compuestos for select to authenticated using (true);
-- Sin políticas de escritura: sólo service_role (que ignora RLS) escribe.
