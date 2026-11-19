-- PowerSync replicates from this publication. Add every table devices receive:
--   alter publication powersync add table public.<new_table>;

create publication powersync for table
  public.profiles,
  public.apiaries,
  public.colonies,
  public.colony_placements;
