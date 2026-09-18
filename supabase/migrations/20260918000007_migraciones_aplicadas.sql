-- ============================================================================
-- Función para que scripts/arrancar.py sepa qué migraciones ya están aplicadas sin
-- necesitar la contraseña de la base: lee supabase_migrations.schema_migrations.
-- Sólo la puede ejecutar service_role.
-- ============================================================================

create or replace function public.migraciones_aplicadas()
returns table (version text, nombre text)
language sql
stable
security definer
set search_path = public
as $$
  select m.version::text, m.name::text
  from supabase_migrations.schema_migrations m
  order by m.version;
$$;

revoke execute on function public.migraciones_aplicadas() from public, anon, authenticated;
grant execute on function public.migraciones_aplicadas() to service_role;
