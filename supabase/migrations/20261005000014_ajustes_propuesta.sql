-- ============================================================================
-- Ajustes del PDF de la propuesta base (pantalla "Formato del PDF").
--   - ajustes: configuración del equipo por clave; `valor` es un jsonb que valida Pydantic
--     (clave 'propuesta_base': título, subtítulo, logotipo, imagen al pie, notas y campos extra), para
--     poder sumar opciones sin migrar.
--   - cotizaciones.campos: valores de los campos extra en cada cotización (id del campo -> texto;
--     las fechas van como AAAA-MM-DD y las horas como HH:MM).
--   - Sólo escribe el backend (service_role); los autenticados pueden leer.
-- ============================================================================

create table public.ajustes (
  clave            text primary key,
  valor            jsonb not null default '{}'::jsonb,
  actualizado_por  uuid references public.perfiles (id) on delete set null,
  actualizado_en   timestamptz not null default now()
);

create index ajustes_actualizado_por_idx on public.ajustes (actualizado_por);

create trigger ajustes_tocar
  before update on public.ajustes
  for each row execute function public.tocar_actualizado_en();

alter table public.ajustes enable row level security;

create policy "ajustes: leer autenticados"
  on public.ajustes for select to authenticated using (true);
-- Sin políticas de escritura: sólo service_role (que ignora RLS) escribe.

alter table public.cotizaciones
  add column campos jsonb not null default '{}'::jsonb;
