-- ============================================================================
-- Precio de los artículos compuestos y cuadre contra el PDF del sistema.
--   - cotizacion_compuestos.precio_modo: cómo se presenta el precio del compuesto.
--       'suma'    -> la suma de sus partidas (no cambia nada; es el valor por defecto);
--       'partida' -> se queda el precio de una de sus partidas (precio_item_id);
--       'manual'  -> un precio unitario que escribe el vendedor (precio_manual).
--     Con 'partida' o 'manual' el importe del compuesto (y el total de la propuesta) puede dejar de
--     coincidir con el PDF del sistema: Revisar lo avisa en rojo.
--   - cotizaciones.subtotal_documento: SubTotal impreso en el PDF del sistema (null si no se encontró
--     o el export es .xlsx). Con él se detecta también una partida que no se haya leído bien.
-- ============================================================================

alter table public.cotizacion_compuestos
  add column precio_modo text not null default 'suma' check (precio_modo in ('suma', 'partida', 'manual')),
  add column precio_item_id uuid,
  add column precio_manual numeric(14, 2) check (precio_manual is null or precio_manual >= 0);

alter table public.cotizaciones
  add column subtotal_documento numeric(14, 2);
