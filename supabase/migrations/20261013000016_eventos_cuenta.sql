-- ============================================================================
-- Avisos de cuenta para el administrador.
-- Cada vez que alguien cambia su propia contraseña desde la aplicación queda un renglón aquí, y
-- también cuando falla al confirmar la contraseña actual (sirve para detectar intentos ajenos).
-- Sólo los admin leen; sólo el backend (service_role) escribe.
-- ============================================================================

create table public.eventos_cuenta (
  id          uuid primary key default gen_random_uuid(),
  usuario_id  uuid references public.perfiles (id) on delete set null,
  tipo        text not null check (tipo in ('cambio_contrasena', 'intento_fallido')),
  detalle     text not null default '',
  visto       boolean not null default false,
  creado_en   timestamptz not null default now()
);

create index eventos_cuenta_creado_idx on public.eventos_cuenta (creado_en desc);
create index eventos_cuenta_usuario_idx on public.eventos_cuenta (usuario_id);
create index eventos_cuenta_sin_ver_idx on public.eventos_cuenta (visto) where not visto;

alter table public.eventos_cuenta enable row level security;

create policy "eventos_cuenta: leer admin"
  on public.eventos_cuenta for select to authenticated using (public.es_admin());
-- Sin políticas de escritura: sólo service_role (que ignora RLS) inserta y marca como visto.
