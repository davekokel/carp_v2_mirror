begin;

create extension if not exists pgcrypto;

create table if not exists public.clutch_instance_treatments (
  id                 uuid primary key default gen_random_uuid(),
  clutch_instance_id uuid not null references public.clutch_instances(id) on delete cascade,
  material_type      text,
  material_code      text,
  material_name      text,
  notes              text,
  created_by         text,
  created_at         timestamptz default now()
);
create index if not exists cit_clutch_idx on public.clutch_instance_treatments (clutch_instance_id);

commit;
