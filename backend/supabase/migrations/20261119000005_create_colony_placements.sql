-- Placements: "colony X was at apiary Y from started_at to ended_at".
-- A move closes the open placement and opens a new one, so history keeps the old site.

create table public.colony_placements (
  id                uuid primary key,  -- generated on the device
  owner_id          uuid not null default auth.uid() references auth.users (id) on delete cascade,
  colony_id         uuid not null references public.colonies (id),
  apiary_id         uuid not null references public.apiaries (id),
  started_at        timestamptz not null,
  ended_at          timestamptz,  -- null = the colony is here now
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  client_updated_at timestamptz not null,
  deleted_at        timestamptz,
  constraint colony_placements_dates_chk check (ended_at is null or ended_at >= started_at)
);

-- At most one open placement per colony.
create unique index colony_placements_one_open_idx
  on public.colony_placements (colony_id)
  where ended_at is null and deleted_at is null;

create index colony_placements_owner_id_idx on public.colony_placements (owner_id);
create index colony_placements_colony_started_idx on public.colony_placements (colony_id, started_at);
create index colony_placements_apiary_id_idx on public.colony_placements (apiary_id);

create trigger colony_placements_set_updated_at
  before update on public.colony_placements
  for each row execute function public.set_updated_at();

alter table public.colony_placements enable row level security;

create policy "colony_placements: select own" on public.colony_placements
  for select to authenticated using (owner_id = (select auth.uid()));

-- Writes must reference the user's own colony and apiary (no cross-user links).
create policy "colony_placements: insert own" on public.colony_placements
  for insert to authenticated with check (
    owner_id = (select auth.uid())
    and exists (select 1 from public.colonies c where c.id = colony_id and c.owner_id = (select auth.uid()))
    and exists (select 1 from public.apiaries a where a.id = apiary_id and a.owner_id = (select auth.uid()))
  );
create policy "colony_placements: update own" on public.colony_placements
  for update to authenticated
  using (owner_id = (select auth.uid()))
  with check (
    owner_id = (select auth.uid())
    and exists (select 1 from public.colonies c where c.id = colony_id and c.owner_id = (select auth.uid()))
    and exists (select 1 from public.apiaries a where a.id = apiary_id and a.owner_id = (select auth.uid()))
  );
