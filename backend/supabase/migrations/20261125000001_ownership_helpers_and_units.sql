-- Shared helpers for record tables: the unit domain and "does this row belong to me" checks
-- used by RLS policies. Each helper returns true for null so optional references pass.

create domain public.measure_unit as text
  check (value in ('ml', 'l', 'g', 'kg', 'pcs', 'strips', 'frames'));

create domain public.record_source as text
  check (value in ('manual', 'voice'));

create or replace function public.owns_colony(colony uuid)
returns boolean language sql stable set search_path = '' as $$
  select colony is null or exists (
    select 1 from public.colonies c where c.id = colony and c.owner_id = (select auth.uid())
  );
$$;

create or replace function public.owns_apiary(apiary uuid)
returns boolean language sql stable set search_path = '' as $$
  select apiary is null or exists (
    select 1 from public.apiaries a where a.id = apiary and a.owner_id = (select auth.uid())
  );
$$;
