-- Voice entry: offline voice notes (synced) and assistant conversation state (server only).

create table public.voice_notes (
  id                 uuid primary key,  -- generated on the device
  owner_id           uuid not null default auth.uid() references auth.users (id) on delete cascade,
  transcript         text not null check (char_length(transcript) between 1 and 4000),
  audio_path         text,
  locale             text not null default 'en-US' check (char_length(locale) between 2 and 20),
  context_colony_id  uuid references public.colonies (id),
  context_apiary_id  uuid references public.apiaries (id),
  status             text not null default 'pending' check (status in (
                       'pending', 'processing', 'needs_answer', 'needs_confirmation',
                       'saved', 'cancelled', 'failed')),
  thread_id          uuid,
  result_record_type text,
  result_record_id   uuid,
  error              text,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now(),
  client_updated_at  timestamptz not null,
  deleted_at         timestamptz
);

create index voice_notes_owner_status_idx on public.voice_notes (owner_id, status);

create trigger voice_notes_set_updated_at
  before update on public.voice_notes
  for each row execute function public.set_updated_at();

alter table public.voice_notes enable row level security;

create policy "voice_notes: select own" on public.voice_notes
  for select to authenticated using (owner_id = (select auth.uid()));
create policy "voice_notes: insert own" on public.voice_notes
  for insert to authenticated with check (
    owner_id = (select auth.uid())
    and public.owns_colony(context_colony_id)
    and public.owns_apiary(context_apiary_id)
  );
create policy "voice_notes: update own" on public.voice_notes
  for update to authenticated
  using (owner_id = (select auth.uid()))
  with check (
    owner_id = (select auth.uid())
    and public.owns_colony(context_colony_id)
    and public.owns_apiary(context_apiary_id)
  );


-- LangGraph conversation state for one voice session (thread). Written ONLY by the API:
-- the state is deserialized server-side, so users must never be able to write it.
-- RLS is on with no policies and no grants for anon/authenticated (blocks PostgREST too).
create table public.voice_sessions (
  id          uuid primary key,  -- the LangGraph thread_id
  owner_id    uuid not null references auth.users (id) on delete cascade,
  status      text not null,
  state       jsonb not null,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create index voice_sessions_owner_id_idx on public.voice_sessions (owner_id);

create trigger voice_sessions_set_updated_at
  before update on public.voice_sessions
  for each row execute function public.set_updated_at();

alter table public.voice_sessions enable row level security;
revoke all on table public.voice_sessions from anon, authenticated;


alter publication powersync add table
  public.inventory_items,
  public.inventory_adjustments,
  public.treatments,
  public.harvests,
  public.colony_notes,
  public.voice_notes;
