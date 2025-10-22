begin;

create extension if not exists pgcrypto;

-- Minimal fish_pairs table used by "Fish pairs → Tank pairs" and referenced by tank_pairs.fish_pair_id
create table if not exists public.fish_pairs (
  id           uuid primary key default gen_random_uuid(),
  mom_fish_id  uuid not null references public.fish(id) on delete cascade,
  dad_fish_id  uuid not null references public.fish(id) on delete cascade,
  created_by   text,
  created_at   timestamptz not null default now()
);

-- Optional: uniqueness if you want one pair per unordered set (mom, dad).
-- This version treats (mom, dad) as ordered; uncomment below for unordered uniqueness.
-- create unique index if not exists fish_pairs_mom_dad_uq on public.fish_pairs (mom_fish_id, dad_fish_id);

create index if not exists fish_pairs_created_idx on public.fish_pairs (created_at desc);

commit;
