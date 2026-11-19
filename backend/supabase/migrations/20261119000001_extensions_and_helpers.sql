-- Extensions and shared helpers used by every domain table.

create extension if not exists postgis with schema extensions;

-- Keeps updated_at (server time) current on every update.
create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;
