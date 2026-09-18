-- ============================================================================
-- Endurecimiento sugerido por el linter de seguridad de Supabase:
--   - search_path fijo en todas las funciones.
--   - Las funciones SECURITY DEFINER no se exponen a anon; la de trigger a nadie.
--     es_admin() sigue disponible para authenticated porque la usan las políticas RLS.
--     resumen_biblioteca() la llama el backend (service_role); authenticated sólo lee
--     datos que ya puede leer por RLS.
-- ============================================================================

alter function public.tocar_actualizado_en() set search_path = public;

revoke execute on function public.al_asignar_imagen() from public, anon, authenticated;
revoke execute on function public.es_admin() from public, anon;
revoke execute on function public.resumen_biblioteca(integer) from public, anon;

grant execute on function public.es_admin() to authenticated, service_role;
grant execute on function public.resumen_biblioteca(integer) to authenticated, service_role;
