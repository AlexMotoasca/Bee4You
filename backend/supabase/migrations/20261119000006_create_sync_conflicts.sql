-- Edits that lost last-write-wins, kept for review. Written by the API, not by devices.

create table public.sync_conflicts (
  id             uuid primary key default gen_random_uuid(),
  owner_id       uuid not null default auth.uid() references auth.users (id) on delete cascade,
  table_name     text not null,
  record_id      uuid not null,
  client_payload jsonb not null,
  server_payload jsonb,
  resolution     text check (resolution in ('kept_server', 'applied_client', 'merged')),
  resolved_at    timestamptz,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);

create index sync_conflicts_owner_open_idx on public.sync_conflicts (owner_id) where resolved_at is null;

create trigger sync_conflicts_set_updated_at
  before update on public.sync_conflicts
  for each row execute function public.set_updated_at();

alter table public.sync_conflicts enable row level security;

create policy "sync_conflicts: select own" on public.sync_conflicts
  for select to authenticated using (owner_id = (select auth.uid()));
create policy "sync_conflicts: insert own" on public.sync_conflicts
  for insert to authenticated with check (owner_id = (select auth.uid()));
create policy "sync_conflicts: update own" on public.sync_conflicts
  for update to authenticated
  using (owner_id = (select auth.uid())) with check (owner_id = (select auth.uid()));
