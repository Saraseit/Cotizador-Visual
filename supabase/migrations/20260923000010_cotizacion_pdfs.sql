-- ============================================================================
-- Historial de PDF generados por cotización (propuesta base y presentación
-- editorial). Cada clic en "Generar" crea un archivo nuevo en Storage; esta
-- tabla lleva el registro para la pantalla "Propuestas", que lista todas las
-- cotizaciones y, por cada una, todos sus PDF listos para descargar e imprimir.
-- Sólo escribe el backend (service_role); los autenticados pueden leer.
-- ============================================================================

create table public.cotizacion_pdfs (
  id             uuid primary key default gen_random_uuid(),
  cotizacion_id  uuid not null references public.cotizaciones (id) on delete cascade,
  tipo           text not null check (tipo in ('base', 'editorial')),
  ruta_storage   text not null,
  generado_por   uuid references public.perfiles (id) on delete set null,
  creado_en      timestamptz not null default now()
);

create index cotizacion_pdfs_cotizacion_creado_idx on public.cotizacion_pdfs (cotizacion_id, creado_en desc);
create index cotizacion_pdfs_generado_por_idx on public.cotizacion_pdfs (generado_por);

alter table public.cotizacion_pdfs enable row level security;

create policy "cotizacion_pdfs: leer autenticados"
  on public.cotizacion_pdfs for select to authenticated using (true);
-- Sin políticas de escritura: sólo service_role (que ignora RLS) inserta.
