-- Run ONCE in the Supabase SQL Editor (Dashboard > SQL Editor > New query).
-- Replace CHANGE_ME with a long random password, and save it in your password manager:
-- you'll paste it into the PowerSync dashboard. Never commit the real password.
--
-- The `powersync` publication already exists (created by our migrations), so it is NOT
-- created here. Only the tables devices receive are readable: no voice_sessions,
-- no sync_conflicts.

create role powersync_role with replication bypassrls login password 'CHANGE_ME';

grant usage on schema public to powersync_role;
grant select on
  public.profiles,
  public.apiaries,
  public.colonies,
  public.colony_placements,
  public.inventory_items,
  public.inventory_adjustments,
  public.treatments,
  public.harvests,
  public.colony_notes,
  public.voice_notes
to powersync_role;

-- st_x / st_y on apiaries.location live in the extensions schema.
grant usage on schema extensions to powersync_role;
