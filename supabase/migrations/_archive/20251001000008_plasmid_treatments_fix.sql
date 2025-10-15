-- Ensure injected_plasmid_treatments has the columns we now expect
-- (idempotent: only adds/creates if missing)

-- 1) Add fish_id if missing
do $$
begin
  if not exists (
    select 1 from information_schema.columns
    where table_schema = 'public'
      and table_name   = 'injected_plasmid_treatments'
      and column_name  = 'fish_id'
  ) then
    alter table public.injected_plasmid_treatments
      add column fish_id uuid;

    -- FK to fish; nullable to avoid failing if you have legacy rows
    alter table public.injected_plasmid_treatments
      add constraint ipt_fish_fk
      foreign key (fish_id) references public.fish(id) on delete cascade;
  end if;
end$$;

-- 2) Add plasmid_id if missing (should exist already, but keep it safe)
do $$
begin
  if not exists (
    select 1 from information_schema.columns
    where table_schema = 'public'
      and table_name   = 'injected_plasmid_treatments'
      and column_name  = 'plasmid_id'
  ) then
    alter table public.injected_plasmid_treatments
      add column plasmid_id uuid;

    alter table public.injected_plasmid_treatments
      add constraint ipt_plasmid_fk
      foreign key (plasmid_id) references public.plasmids(id_uuid) on delete restrict;
  end if;
end$$;

-- 3) Add optional detail columns if missing (amount, units, at_time, note)
do $$
begin
  if not exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='injected_plasmid_treatments' and column_name='amount'
  ) then
    alter table public.injected_plasmid_treatments add column amount numeric;
  end if;

  if not exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='injected_plasmid_treatments' and column_name='units'
  ) then
    alter table public.injected_plasmid_treatments add column units text;
  end if;

  if not exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='injected_plasmid_treatments' and column_name='at_time'
  ) then
    alter table public.injected_plasmid_treatments add column at_time timestamptz;
  end if;

  if not exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='injected_plasmid_treatments' and column_name='note'
  ) then
    alter table public.injected_plasmid_treatments add column note text;
  end if;
end$$;

-- 4) Recreate the natural de-dupe index (safe replace)
drop index if exists uq_ipt_natural;
create unique index if not exists uq_ipt_natural
  on public.injected_plasmid_treatments (fish_id, plasmid_id, at_time, amount, units, note);
