-- Harvests (apiary-level, optionally per colony) and colony notes / inspections.

create table public.harvests (
  id                uuid primary key,
  owner_id          uuid not null default auth.uid() references auth.users (id) on delete cascade,
  apiary_id         uuid not null references public.apiaries (id),
  colony_id         uuid references public.colonies (id),
  quantity          numeric not null check (quantity > 0),
  unit              public.measure_unit not null,
  harvested_at      timestamptz not null,
  notes             text check (char_length(notes) <= 2000),
  source            public.record_source not null default 'manual',
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  client_updated_at timestamptz not null,
  deleted_at        timestamptz
);

create index harvests_owner_id_idx on public.harvests (owner_id);
create index harvests_apiary_harvested_idx on public.harvests (apiary_id, harvested_at);

create trigger harvests_set_updated_at
  before update on public.harvests
  for each row execute function public.set_updated_at();

alter table public.harvests enable row level security;

create policy "harvests: select own" on public.harvests
  for select to authenticated using (owner_id = (select auth.uid()));
create policy "harvests: insert own" on public.harvests
  for insert to authenticated with check (
    owner_id = (select auth.uid()) and public.owns_apiary(apiary_id) and public.owns_colony(colony_id)
  );
create policy "harvests: update own" on public.harvests
  for update to authenticated
  using (owner_id = (select auth.uid()))
  with check (
    owner_id = (select auth.uid()) and public.owns_apiary(apiary_id) and public.owns_colony(colony_id)
  );


create table public.colony_notes (
  id                uuid primary key,
  owner_id          uuid not null default auth.uid() references auth.users (id) on delete cascade,
  colony_id         uuid not null references public.colonies (id),
  apiary_id         uuid not null references public.apiaries (id),
  noted_at          timestamptz not null,
  queen_seen        boolean,
  temperament       text check (temperament in ('calm', 'nervous', 'aggressive')),
  text              text check (char_length(text) <= 4000),
  source            public.record_source not null default 'manual',
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  client_updated_at timestamptz not null,
  deleted_at        timestamptz,
  constraint colony_notes_not_empty_chk
    check (queen_seen is not null or temperament is not null or coalesce(text, '') <> '')
);

create index colony_notes_owner_id_idx on public.colony_notes (owner_id);
create index colony_notes_colony_noted_idx on public.colony_notes (colony_id, noted_at);

create trigger colony_notes_set_updated_at
  before update on public.colony_notes
  for each row execute function public.set_updated_at();

alter table public.colony_notes enable row level security;

create policy "colony_notes: select own" on public.colony_notes
  for select to authenticated using (owner_id = (select auth.uid()));
create policy "colony_notes: insert own" on public.colony_notes
  for insert to authenticated with check (
    owner_id = (select auth.uid()) and public.owns_colony(colony_id) and public.owns_apiary(apiary_id)
  );
create policy "colony_notes: update own" on public.colony_notes
  for update to authenticated
  using (owner_id = (select auth.uid()))
  with check (
    owner_id = (select auth.uid()) and public.owns_colony(colony_id) and public.owns_apiary(apiary_id)
  );
