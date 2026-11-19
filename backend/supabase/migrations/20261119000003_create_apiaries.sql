-- Apiaries: sites where colonies are placed. Location is synced to devices as lat/lng.

create table public.apiaries (
  id                uuid primary key,  -- generated on the device
  owner_id          uuid not null default auth.uid() references auth.users (id) on delete cascade,
  name              text not null check (char_length(name) between 1 and 120),
  kind              text not null default 'permanent' check (kind in ('permanent', 'temporary')),
  location          extensions.geography (point, 4326),
  notes             text check (char_length(notes) <= 2000),
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  client_updated_at timestamptz not null,
  deleted_at        timestamptz
);

create index apiaries_owner_id_idx on public.apiaries (owner_id);
create index apiaries_location_idx on public.apiaries using gist (location);

create trigger apiaries_set_updated_at
  before update on public.apiaries
  for each row execute function public.set_updated_at();

alter table public.apiaries enable row level security;

create policy "apiaries: select own" on public.apiaries
  for select to authenticated using (owner_id = (select auth.uid()));
create policy "apiaries: insert own" on public.apiaries
  for insert to authenticated with check (owner_id = (select auth.uid()));
create policy "apiaries: update own" on public.apiaries
  for update to authenticated
  using (owner_id = (select auth.uid())) with check (owner_id = (select auth.uid()));
-- No delete policy: records are soft-deleted (deleted_at) so devices receive tombstones.
