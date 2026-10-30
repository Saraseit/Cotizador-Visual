-- ============================================================================
-- Fecha del evento en la cotización.
-- El export del sistema no la trae (sólo cliente, teléfono y número de cotización), así que la
-- captura la vendedora en Revisar. Es la fecha que se imprime en el encabezado de la propuesta:
-- antes salía la de generación del PDF, que al cliente no le dice nada.
-- `fecha_evento_fin` sólo para eventos de varios días; vacía en la mayoría.
-- ============================================================================

alter table public.cotizaciones
  add column fecha_evento     date,
  add column fecha_evento_fin date;

-- Un cierre sin inicio no significa nada, y terminar antes de empezar tampoco.
alter table public.cotizaciones
  add constraint cotizaciones_fecha_evento_rango check (
    fecha_evento_fin is null
    or (fecha_evento is not null and fecha_evento_fin >= fecha_evento)
  );

comment on column public.cotizaciones.fecha_evento is
  'Día del evento; se imprime en el encabezado de la propuesta.';
comment on column public.cotizaciones.fecha_evento_fin is
  'Último día, sólo si el evento dura varios días.';
