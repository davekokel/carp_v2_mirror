begin;

create extension if not exists pgcrypto;

-- Core "crosses" identity (kept for backward compatibility; tank-centric pages may bypass it)
create table if not exists public.crosses (
  id uuid primary key default gen_random_uuid(),
  mother_code text,
  father_code text,
  cross_code  text unique,
  created_by  text,
  created_at  timestamptz default now()
);

-- One run of a cross on a given date (tank-centric fields included)
create table if not exists public.cross_instances (
  id uuid primary key default gen_random_uuid(),
  cross_id uuid references public.crosses(id) on delete set null,
  tank_pair_id uuid,                         -- tank-centric key; may be null in legacy rows
  cross_run_code text,
  cross_date date,
  note text,
  created_by text,
  created_at timestamptz default now()
);
create index if not exists cross_instances_date_idx on public.cross_instances(cross_date desc);
create index if not exists cross_instances_pair_idx on public.cross_instances(tank_pair_id);

-- Planned clutches (concepts)
create table if not exists public.clutch_plans (
  id uuid primary key default gen_random_uuid(),
  clutch_code text unique,
  name text,
  nickname text,
  mom_code text,
  dad_code text,
  tank_pair_id uuid,
  date_planned date,
  created_by text,
  created_at timestamptz default now()
);

-- Legacy link from plan → cross (kept for compatibility)
create table if not exists public.planned_crosses (
  clutch_id uuid references public.clutch_plans(id) on delete cascade,
  cross_id  uuid references public.crosses(id)      on delete cascade,
  mother_tank_id uuid,
  father_tank_id uuid,
  created_at timestamptz default now(),
  primary key(clutch_id, cross_id)
);

-- Resulting clutch instance (what you annotate)
create table if not exists public.clutch_instances (
  id uuid primary key default gen_random_uuid(),
  cross_instance_id uuid references public.cross_instances(id) on delete cascade,
  clutch_instance_code text,
  label text,
  date_birth date,
  red_selected boolean,
  red_intensity text,
  green_selected boolean,
  green_intensity text,
  notes text,
  annotated_by text,
  annotated_at timestamptz,
  created_at timestamptz default now()
);
create index if not exists clutch_instances_x_idx on public.clutch_instances(cross_instance_id);

commit;
