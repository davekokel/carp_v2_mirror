begin;

-- Ensure id-based columns exist (no-op if already there)
alter table public.fish_pairs
  add column if not exists mom_fish_id uuid,
  add column if not exists dad_fish_id uuid;

-- Optional but recommended: enforce referential integrity
do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'fk_fish_pairs_mom_id' and conrelid = 'public.fish_pairs'::regclass
  ) then
    alter table public.fish_pairs
      add constraint fk_fish_pairs_mom_id
      foreign key (mom_fish_id) references public.fish(id) on delete restrict;
  end if;

  if not exists (
    select 1 from pg_constraint
    where conname = 'fk_fish_pairs_dad_id' and conrelid = 'public.fish_pairs'::regclass
  ) then
    alter table public.fish_pairs
      add constraint fk_fish_pairs_dad_id
      foreign key (dad_fish_id) references public.fish(id) on delete restrict;
  end if;
end $$;

-- Unique identity for the (unordered) pair.
-- (Your app canonicalizes the order before insert, so one index is enough.)
create unique index if not exists ux_fish_pairs_mom_dad
  on public.fish_pairs(mom_fish_id, dad_fish_id);

commit;
