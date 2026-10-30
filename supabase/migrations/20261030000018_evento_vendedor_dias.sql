-- ============================================================================
-- Vendedor y días de renta en la cotización.
--
-- El export del sistema trae "Atendió:" y "DIAS:"; el sistema multiplica el mobiliario por DIAS
-- (flete y montaje se cobran una vez), así que ProVista tiene que hacer la misma cuenta o la
-- propuesta no cuadra con el sistema.
--   - vendedor:        quién atiende al cliente. Sale del "Atendió:" del export; se puede corregir.
--   - dias_documento:  DIAS tal como venía en el export (null = no se leyó; cuenta como 1).
--   - dias_renta:      cuántos días tiene el cliente el mobiliario.
--   - dias_cobrados:   cuántos se cobran. null = los mismos que los de renta (la casilla
--                      "días de renta = cobrados"); distinto cuando hay promoción o acuerdo.
-- ============================================================================

alter table public.cotizaciones
  add column vendedor       text not null default '',
  add column dias_documento numeric(6, 1),
  add column dias_renta     numeric(6, 1) not null default 1,
  add column dias_cobrados  numeric(6, 1);

alter table public.cotizaciones
  add constraint cotizaciones_dias_validos check (
    dias_renta > 0
    and (dias_cobrados is null or dias_cobrados > 0)
    and (dias_documento is null or dias_documento > 0)
  );

comment on column public.cotizaciones.vendedor is
  'Quién atiende al cliente; sale del "Atendió:" del export y se imprime en la propuesta.';
comment on column public.cotizaciones.dias_documento is
  'DIAS del export del sistema (null = no se leyó, cuenta como 1). Con él se reconstruye el SubTotal del sistema.';
comment on column public.cotizaciones.dias_renta is
  'Días que el cliente tiene el mobiliario.';
comment on column public.cotizaciones.dias_cobrados is
  'Días que se cobran; null = los mismos que dias_renta. El mobiliario se multiplica por éstos.';
