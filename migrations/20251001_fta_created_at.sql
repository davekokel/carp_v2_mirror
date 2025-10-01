-- 20251001_fta_created_at.sql
-- Add created_at to link table (if you want audit timestamps)

begin;

alter table public.fish_transgene_alleles
  add column if not exists created_at timestamptz not null default now();

commit;
