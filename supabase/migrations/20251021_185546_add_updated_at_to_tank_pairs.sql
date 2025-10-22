begin;
alter table if exists public.tank_pairs
  add column if not exists updated_at timestamptz;
commit;
