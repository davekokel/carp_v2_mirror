begin;

-- Ensure pgcrypto for gen_random_uuid()
create extension if not exists pgcrypto;

-- Create the table if missing (minimal shape the generator expects)
create table if not exists public.clutches (
  id                uuid primary key default gen_random_uuid(),
  clutch_code       text,                    -- generator/trigger will manage
  expected_genotype text,
  fish_pair_id      uuid,
  fish_pair_code    text,
  created_by        text,
  created_at        timestamptz not null default now()
);

-- Be defensive: add any missing columns if table already existed
do $$
begin
  if not exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='clutches' and column_name='clutch_code'
  ) then
    alter table public.clutches add column clutch_code text;
  end if;

  if not exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='clutches' and column_name='expected_genotype'
  ) then
    alter table public.clutches add column expected_genotype text;
  end if;

  if not exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='clutches' and column_name='fish_pair_id'
  ) then
    alter table public.clutches add column fish_pair_id uuid;
  end if;

  if not exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='clutches' and column_name='fish_pair_code'
  ) then
    alter table public.clutches add column fish_pair_code text;
  end if;

  if not exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='clutches' and column_name='created_by'
  ) then
    alter table public.clutches add column created_by text;
  end if;

  if not exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='clutches' and column_name='created_at'
  ) then
    alter table public.clutches add column created_at timestamptz not null default now();
  end if;
end$$;

commit;
