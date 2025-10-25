begin;

create table if not exists public.tank_pairs (
  id uuid primary key default gen_random_uuid(),
  fish_pair_id uuid,           -- FK optional
  mother_tank_id uuid,
  father_tank_id uuid,
  tank_pair_code text unique,
  concept_id uuid,
  status text default 'selected',
  created_by text,
  created_at timestamptz default now()
);

comment on table public.tank_pairs is 'tank-centric pairing table; joins mom/dad tanks';

commit;
