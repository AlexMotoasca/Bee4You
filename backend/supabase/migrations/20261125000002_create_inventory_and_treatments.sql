-- Inventory items, treatments, and inventory adjustments (stock = sum of adjustments).
-- Treatments come before adjustments because an adjustment can point at the treatment
-- that used the stock.

create table public.inventory_items (
  id                uuid primary key,  -- generated on the device
  owner_id          uuid not null default auth.uid() references auth.users (id) on delete cascade,
  name              text not null check (char_length(name) between 1 and 120),
  category          text not null default 'other'
                      check (category in ('treatment', 'equipment', 'consumable', 'other')),
  unit              public.measure_unit not null,
  apiary_id         uuid references public.apiaries (id),  -- null = home / store
  notes             text check (char_length(notes) <= 2000),
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  client_updated_at timestamptz not null,
  deleted_at        timestamptz
);

create index inventory_items_owner_id_idx on public.inventory_items (owner_id);

create trigger inventory_items_set_updated_at
  before update on public.inventory_items
  for each row execute function public.set_updated_at();

alter table public.inventory_items enable row level security;

create policy "inventory_items: select own" on public.inventory_items
  for select to authenticated using (owner_id = (select auth.uid()));
create policy "inventory_items: insert own" on public.inventory_items
  for insert to authenticated
  with check (owner_id = (select auth.uid()) and public.owns_apiary(apiary_id));
create policy "inventory_items: update own" on public.inventory_items
  for update to authenticated
  using (owner_id = (select auth.uid()))
  with check (owner_id = (select auth.uid()) and public.owns_apiary(apiary_id));

create or replace function public.owns_inventory_item(item uuid)
returns boolean language sql stable set search_path = '' as $$
  select item is null or exists (
    select 1 from public.inventory_items i where i.id = item and i.owner_id = (select auth.uid())
  );
$$;


create table public.treatments (
  id                uuid primary key,
  owner_id          uuid not null default auth.uid() references auth.users (id) on delete cascade,
  colony_id         uuid not null references public.colonies (id),
  apiary_id         uuid not null references public.apiaries (id),  -- where it happened
  inventory_item_id uuid references public.inventory_items (id),
  product_name      text not null check (char_length(product_name) between 1 and 120),
  amount            numeric not null check (amount > 0),
  unit              public.measure_unit not null,
  treated_at        timestamptz not null,
  notes             text check (char_length(notes) <= 2000),
  source            public.record_source not null default 'manual',
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  client_updated_at timestamptz not null,
  deleted_at        timestamptz
);

create index treatments_owner_id_idx on public.treatments (owner_id);
create index treatments_colony_treated_idx on public.treatments (colony_id, treated_at);

create trigger treatments_set_updated_at
  before update on public.treatments
  for each row execute function public.set_updated_at();

alter table public.treatments enable row level security;

create policy "treatments: select own" on public.treatments
  for select to authenticated using (owner_id = (select auth.uid()));
create policy "treatments: insert own" on public.treatments
  for insert to authenticated with check (
    owner_id = (select auth.uid())
    and public.owns_colony(colony_id)
    and public.owns_apiary(apiary_id)
    and public.owns_inventory_item(inventory_item_id)
  );
create policy "treatments: update own" on public.treatments
  for update to authenticated
  using (owner_id = (select auth.uid()))
  with check (
    owner_id = (select auth.uid())
    and public.owns_colony(colony_id)
    and public.owns_apiary(apiary_id)
    and public.owns_inventory_item(inventory_item_id)
  );

create or replace function public.owns_treatment(treatment uuid)
returns boolean language sql stable set search_path = '' as $$
  select treatment is null or exists (
    select 1 from public.treatments t where t.id = treatment and t.owner_id = (select auth.uid())
  );
$$;


create table public.inventory_adjustments (
  id                uuid primary key,
  owner_id          uuid not null default auth.uid() references auth.users (id) on delete cascade,
  item_id           uuid not null references public.inventory_items (id),
  delta             numeric not null check (delta <> 0),
  unit              public.measure_unit not null,
  reason            text not null check (reason in ('purchase', 'used', 'moved', 'correction')),
  apiary_id         uuid references public.apiaries (id),
  adjusted_at       timestamptz not null,
  treatment_id      uuid references public.treatments (id),  -- set when a treatment used stock
  notes             text check (char_length(notes) <= 2000),
  source            public.record_source not null default 'manual',
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  client_updated_at timestamptz not null,
  deleted_at        timestamptz
);

create index inventory_adjustments_owner_id_idx on public.inventory_adjustments (owner_id);
create index inventory_adjustments_item_idx on public.inventory_adjustments (item_id);
-- A treatment uses stock at most once.
create unique index inventory_adjustments_one_per_treatment_idx
  on public.inventory_adjustments (treatment_id)
  where treatment_id is not null and deleted_at is null;

create trigger inventory_adjustments_set_updated_at
  before update on public.inventory_adjustments
  for each row execute function public.set_updated_at();

alter table public.inventory_adjustments enable row level security;

create policy "inventory_adjustments: select own" on public.inventory_adjustments
  for select to authenticated using (owner_id = (select auth.uid()));
create policy "inventory_adjustments: insert own" on public.inventory_adjustments
  for insert to authenticated with check (
    owner_id = (select auth.uid())
    and public.owns_inventory_item(item_id)
    and public.owns_apiary(apiary_id)
    and public.owns_treatment(treatment_id)
  );
create policy "inventory_adjustments: update own" on public.inventory_adjustments
  for update to authenticated
  using (owner_id = (select auth.uid()))
  with check (
    owner_id = (select auth.uid())
    and public.owns_inventory_item(item_id)
    and public.owns_apiary(apiary_id)
    and public.owns_treatment(treatment_id)
  );
