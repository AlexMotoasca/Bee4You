-- Colonies (hives). Where a colony is lives in colony_placements, not here.

create table public.colonies (
  id                uuid primary key,  -- generated on the device
  owner_id          uuid not null default auth.uid() references auth.users (id) on delete cascade,
  label             text not null check (char_length(label) between 1 and 60),
  number            integer check (number >= 0),  -- "hive 12" for voice matching; not unique
  mode              text not null default 'stationary' check (mode in ('stationary', 'migratory')),
  status            text not null default 'active'
                      check (status in ('active', 'dead', 'sold', 'merged')),
  queen_year        integer check (queen_year between 1990 and 2100),
  notes             text check (char_length(notes) <= 2000),
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  client_updated_at timestamptz not null,
  deleted_at        timestamptz
);

create index colonies_owner_id_idx on public.colonies (owner_id);
create index colonies_owner_number_idx on public.colonies (owner_id, number);

create trigger colonies_set_updated_at
  before update on public.colonies
  for each row execute function public.set_updated_at();

alter table public.colonies enable row level security;

create policy "colonies: select own" on public.colonies
  for select to authenticated using (owner_id = (select auth.uid()));
create policy "colonies: insert own" on public.colonies
  for insert to authenticated with check (owner_id = (select auth.uid()));
create policy "colonies: update own" on public.colonies
  for update to authenticated
  using (owner_id = (select auth.uid())) with check (owner_id = (select auth.uid()));
