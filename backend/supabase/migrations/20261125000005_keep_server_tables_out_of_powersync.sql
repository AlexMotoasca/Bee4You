-- PowerSync's "Set Up with Supabase" adds every table to the `powersync` publication and
-- grants its database user SELECT on all of them. Server-only tables must not be replicated
-- to PowerSync: voice_sessions holds transcripts and assistant state, sync_conflicts holds
-- raw rejected payloads. Phones never receive them anyway (not in sync-config.yaml).
--
-- Idempotent: safe to re-run (copy into the SQL Editor) if PowerSync's setup runs again.

do $$
declare
  r record;
begin
  for r in
    select tablename from pg_publication_tables
    where pubname = 'powersync'
      and schemaname = 'public'
      and tablename in ('voice_sessions', 'sync_conflicts')
  loop
    execute format('alter publication powersync drop table public.%I', r.tablename);
  end loop;

  for r in select rolname from pg_roles where rolname like 'powersync%' loop
    execute format('revoke all on table public.voice_sessions, public.sync_conflicts from %I', r.rolname);
  end loop;
end
$$;
